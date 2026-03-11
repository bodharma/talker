# The Shard Receptionist — LiveKit Voice Agent

A voice-based AI receptionist for The Shard in London. A guest walks in, the agent greets them, figures out who they're visiting, looks them up in the building directory, and tells them which floor to go to — handling edge cases naturally along the way.

## Quick start

```bash
# Install
git clone https://github.com/bodharma/talker.git
cd talker
uv sync

# Configure — only LiveKit credentials needed
cp .env.receptionist .env
# Edit .env — add LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
# from your LiveKit Cloud dashboard (https://cloud.livekit.io)

# Run
uv run python -m talker.livekit_agent --persona receptionist

# Connect via LiveKit Playground
# https://agents-playground.livekit.io → enter your LiveKit Cloud URL → connect
```

No database, no OpenAI key, no extra services. LiveKit free tier (sign up with GitHub) includes STT, LLM, and TTS out of the box.

### Environment variables

| Variable | Required | What it does |
|---|---|---|
| `LIVEKIT_URL` | Yes | Your LiveKit Cloud WebSocket URL |
| `LIVEKIT_API_KEY` | Yes | From LiveKit Cloud dashboard |
| `LIVEKIT_API_SECRET` | Yes | From LiveKit Cloud dashboard |
| `OPENWEATHERMAP_API_KEY` | No | Real London weather — falls back to mock if not set |
| `DATABASE_URL` | No | PostgreSQL for visitor tracking — disabled if empty |

All of these are in `.env.receptionist` ready to fill in.

## What happens in a conversation

1. **Greeting** — warm, professional welcome to The Shard
2. **Visitor identification** — who are you here to see? (name, company)
3. **Directory lookup** — tool call to find the tenant, return floor and suite
4. **Edge cases handled naturally:**
   - Person not found → offer to check spelling, suggest similar names
   - Visitee unavailable / out of office → offer to wait, direct to coffee bar
   - Building questions → bathrooms, parking, restaurants, observation deck
   - Weather → live London weather via API (or mock fallback)
   - Small talk → the view from the 72nd floor, restaurant recommendations

### Tool calls

| Tool | What it does | Data source |
|---|---|---|
| `lookup_tenant` | Search building directory by name or company | In-memory dict (12 tenants, fuzzy matching) |
| `check_availability` | Is the person available right now? | Preset unavailability + random chance |
| `get_building_info` | Facilities, transport, restaurants, amenities | Static dict (15 topics) |
| `get_weather` | Current London weather | OpenWeatherMap API (real) or mock fallback |
| `log_visitor` | Record the visit for security | PostgreSQL when configured, console fallback |
| `recognize_visitor` | Find a returning visitor by email or name | PostgreSQL visitor tracking |
| `register_visitor` | Silently register a new visitor | PostgreSQL visitor tracking |

The last 3 tools (log, recognize, register) require a database. Without one they gracefully degrade — the receptionist still works, it just doesn't remember visitors between sessions.

### What makes it feel human

- Doesn't interrogate — asks naturally, one thing at a time
- Handles "I don't know the exact name" gracefully (fuzzy matching)
- Small talk capable — weather, the view, restaurant recommendations
- Knows when to stop asking and just help
- Adapts tone based on voice analysis — if a visitor sounds anxious, the agent is warmer and more reassuring; if they're in a rush, it's efficient and direct
- Remembers returning visitors silently — never says "let me register you", just remembers like a good receptionist

---

## Code guide

### Files to read (in this order)

| File | What it does | Lines |
|---|---|---|
| [`talker/personas/receptionist.py`](../talker/personas/receptionist.py) | **The main deliverable.** All 7 tool functions, building directory data, system prompt, and the `ReceptionistAgent` class. Start here. | ~510 |
| [`talker/livekit_agent.py`](../talker/livekit_agent.py) | Agent entrypoint. Persona registry, capability wiring, audio processing pipeline, session setup. | ~200 |
| [`talker/capabilities/voice_analysis.py`](../talker/capabilities/voice_analysis.py) | Voice mood inference — extracts pitch/jitter/shimmer from audio, infers mood (6 rules), injects context into LLM. | ~230 |
| [`talker/capabilities/base.py`](../talker/capabilities/base.py) | Capability ABC — the interface that pluggable pipeline modules implement. | ~50 |
| [`talker/config.py`](../talker/config.py) | All settings via pydantic-settings. Shows every knob available. | ~90 |

### Tests to run

```bash
# Receptionist tools + data integrity (29 tests)
uv run pytest tests/test_receptionist.py -v

# Voice analysis + mood inference (21 tests)
uv run pytest tests/test_capabilities.py -v

# LiveKit routes — token generation, auth gating (6 tests)
uv run pytest tests/test_livekit_routes.py -v

# Everything (201 tests — includes the wider platform)
uv run pytest -v
```

### How the pieces connect

```
.env.receptionist          ← only 3 vars needed (LiveKit credentials)
    │
    ▼
talker/livekit_agent.py    ← entrypoint: loads persona, wires capabilities, starts session
    │
    ├── talker/personas/receptionist.py
    │       ├── DIRECTORY (12 tenants)     ← lookup_tenant, check_availability
    │       ├── BUILDING_INFO (15 topics)  ← get_building_info
    │       ├── get_weather()              ← OpenWeatherMap API / mock
    │       ├── log_visitor()              ← DB or console
    │       ├── recognize_visitor()        ← DB or graceful skip
    │       ├── register_visitor()         ← DB or graceful skip
    │       └── ReceptionistAgent(Agent)   ← instructions + tools
    │
    ├── talker/capabilities/voice_analysis.py
    │       ├── infer_mood()               ← 6 acoustic rules
    │       ├── process_audio()            ← Parselmouth feature extraction
    │       └── get_context_prompt()       ← injects mood into LLM context
    │
    └── LiveKit Cloud (STT → LLM → TTS)
            ├── Deepgram Nova-3 (speech-to-text)
            ├── GPT-4.1-mini (reasoning + tool calls)
            └── Cartesia Sonic-3 (text-to-speech)
```

### Design decisions

**Persona as configuration, not code** — the receptionist and assessor share the same agent engine. A persona is: tools + system prompt + capabilities. Adding a new persona = a Python file and a registry entry.

**Tools are plain functions** — each `@function_tool()` is independently testable. The directory lookup doesn't know or care that it's being called by a voice agent. Tests call `tool._func(None, args)` directly.

**Capabilities vs tools** — tools are called by the LLM on demand ("look up Sarah Chen"). Capabilities run automatically on every audio turn and inject context before the LLM responds ("the visitor sounds anxious"). Different mechanisms, different purposes.

**LiveKit as transport, not architecture** — LiveKit handles the room and STT/LLM/TTS pipeline. The agent logic is framework-agnostic and could run on a different transport without changing the tools or instructions.

---

## Wider platform

This receptionist is one persona on a platform built for structured voice conversations. The same architecture powers a psychology pre-assessment agent with validated DSM-5 screening questionnaires, LLM-powered follow-up conversations, crisis detection, and clinical reports. See the [main README](../README.md) for the full picture.
