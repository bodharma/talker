"""LiveKit voice agent entrypoint — persona-driven voice AI with pluggable capabilities."""

import argparse
import asyncio
import sys
from typing import Any

import numpy as np
from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import AgentServer, AgentSession, Agent, room_io
from livekit.plugins import noise_cancellation, silero
from livekit.plugins.openai import LLM
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from talker.capabilities.base import BaseCapability
from talker.capabilities.voice_analysis import VoiceAnalysisCapability
from talker.config import get_settings
from talker.personas.assessor import AssessorAgent
from talker.personas.receptionist import ReceptionistAgent, set_db_session_factory
from talker.services.database import create_session_factory

load_dotenv()

# Wire up DB for visitor tracking
_settings = get_settings()
if _settings.database_url:
    try:
        _db_factory = create_session_factory(_settings)
        set_db_session_factory(_db_factory)
    except Exception:
        pass  # DB not available — visitor tracking disabled


# ---------------------------------------------------------------------------
# Persona registry — each entry: (agent_class, capabilities)
# ---------------------------------------------------------------------------

PERSONAS: dict[str, dict[str, Any]] = {
    "receptionist": {
        "agent_class": ReceptionistAgent,
        "capabilities": [VoiceAnalysisCapability],
        "greeting": "Greet the visitor warmly. You're at the front desk of The Shard.",
    },
    "receptionist-basic": {
        "agent_class": ReceptionistAgent,
        "capabilities": [],
        "greeting": "Greet the visitor warmly. You're at the front desk of The Shard.",
    },
    "assessor": {
        "agent_class": AssessorAgent,
        "capabilities": [VoiceAnalysisCapability],
        "greeting": (
            "Greet the user warmly. Introduce yourself as a psychology "
            "pre-assessment assistant. Explain what you do and what you don't do "
            "(you're not a therapist or doctor, you can't diagnose). "
            "Ask how they're feeling today."
        ),
    },
    "assessor-basic": {
        "agent_class": AssessorAgent,
        "capabilities": [],
        "greeting": (
            "Greet the user warmly. Introduce yourself as a psychology "
            "pre-assessment assistant. Ask how they're feeling today."
        ),
    },
}


def _build_agent(persona_name: str) -> tuple[Agent, list[BaseCapability], str]:
    """Build an agent instance with its capabilities wired in."""
    config = PERSONAS.get(persona_name)
    if not config:
        print(f"Unknown persona: {persona_name}. Available: {', '.join(PERSONAS)}")
        sys.exit(1)

    agent: Agent = config["agent_class"]()
    capabilities = [cap_cls() for cap_cls in config["capabilities"]]

    # Inject capability tools into the agent
    for cap in capabilities:
        cap_tools = cap.get_tools()
        if cap_tools:
            agent._tools.extend(cap_tools)

    return agent, capabilities, config["greeting"]


# ---------------------------------------------------------------------------
# Audio processing — feeds capabilities with raw audio from the room
# ---------------------------------------------------------------------------


async def _process_audio_stream(
    track: rtc.RemoteAudioTrack,
    capabilities: list[BaseCapability],
    agent: Agent,
):
    """Collect audio frames from a participant track and feed to capabilities."""
    audio_stream = rtc.AudioStream(track)
    buffer: list[np.ndarray] = []
    sample_rate = 16000

    async for event in audio_stream:
        frame = event.frame
        sample_rate = frame.sample_rate

        # Convert frame to numpy
        frame_data = np.frombuffer(frame.data, dtype=np.int16).astype(np.float64) / 32768.0
        buffer.append(frame_data)

        # Process in ~2 second chunks
        total_samples = sum(len(f) for f in buffer)
        if total_samples >= sample_rate * 2:
            audio = np.concatenate(buffer)
            buffer.clear()

            for cap in capabilities:
                try:
                    results = await cap.process_audio(audio, sample_rate)
                    context_prompt = cap.get_context_prompt(results)
                    if context_prompt:
                        # Inject into agent's context for next LLM turn
                        agent._extra_context = getattr(agent, "_extra_context", "") + context_prompt
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning("Capability %s failed: %s", cap.name, e)

    await audio_stream.aclose()


# ---------------------------------------------------------------------------
# Agent session
# ---------------------------------------------------------------------------

_active_persona: str = "receptionist"

server = AgentServer()


@server.rtc_session(agent_name="talker")
async def talker_session(ctx: agents.JobContext):
    agent, capabilities, greeting = _build_agent(_active_persona)

    # Use OpenRouter for LLM if configured, otherwise fall back to OpenAI
    settings = get_settings()
    if settings.openrouter_api_key:
        llm = LLM.with_openrouter(
            model=settings.livekit_llm_model,
            api_key=settings.openrouter_api_key,
        )
    else:
        llm = settings.livekit_llm_model

    session = AgentSession(
        stt=settings.livekit_stt_model,
        llm=llm,
        tts=settings.livekit_tts_model,
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel(),
    )

    # If capabilities need audio, tap into participant tracks
    if capabilities:
        @ctx.room.on("track_subscribed")
        def on_track_subscribed(track: rtc.Track, *_):
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                asyncio.create_task(
                    _process_audio_stream(track, capabilities, agent)
                )

    await session.start(
        room=ctx.room,
        agent=agent,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=noise_cancellation.BVC(),
            ),
        ),
    )

    await session.generate_reply(instructions=greeting)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Talker LiveKit Agent")
    parser.add_argument(
        "--persona",
        default="receptionist",
        choices=list(PERSONAS.keys()),
        help="Which persona to run (default: receptionist)",
    )
    args, remaining = parser.parse_known_args()
    _active_persona = args.persona

    sys.argv = [sys.argv[0]] + remaining
    agents.cli.run_app(server)
