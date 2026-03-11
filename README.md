# Talker

A voice-first AI agent platform for structured conversations with real-world purpose.

The first use case — and the one I care about most — is **psychology pre-assessment**: validated DSM-5 screening questionnaires delivered via voice or text, followed by an LLM-powered conversational follow-up. It's not a medical tool. It's a guide that helps people understand their symptoms and know where to seek professional help.

But the architecture isn't locked to psychology. The agent layer is persona-driven — the same orchestrator, tool registry, and voice pipeline that powers a clinical screener can power a building receptionist, a customer intake agent, or anything else that needs structured human-like conversation with tool access. Swap the prompt and the tools, keep everything else.

## How I got here

I've been building this on my own time because I'm genuinely obsessed with the intersection of voice AI and psychology. The screening instruments (PHQ-9, GAD-7, PCL-5, ASRS) are ones I've studied and used in practice. The safety system exists because this domain demands it — every user message runs through crisis detection before anything else happens.

After meeting Dave and seeing the LiveKit voice agent task, I didn't want to start from scratch or build a throwaway demo. The Shard receptionist scenario maps directly onto what I was already building — a conversational agent with persona-specific tools and natural human interaction. So I integrated LiveKit as a voice transport and added the receptionist as a second persona on the same platform.

**For Dave's specific task** — the Shard receptionist agent built on LiveKit — see [`docs/livekit-receptionist.md`](docs/livekit-receptionist.md).

## What it does

**Voice pipeline** — STT-to-LLM-to-TTS, running locally (faster-whisper + Piper), via cloud providers (Deepgram + ElevenLabs), or through LiveKit rooms.

**Structured screening** — YAML-driven instruments. Adding a new questionnaire means adding a YAML file, not writing code. Scoring, severity thresholds, and flag rules are all data.

**LLM conversation** — PydanticAI agents with tool calling. The conversation agent explores flagged areas from screening results, grounded by RAG context from a clinical knowledge base.

**Safety first** — regex-based crisis detection on every message (zero latency, zero cost, deterministic). 10 patterns covering suicidal ideation, self-harm, and harm to others. Resources served immediately.

**Persona system** — prompts managed via Langfuse. Switch the persona and tools, get a different agent. Psychology assessor and Shard receptionist run on the same engine.

**Multi-user auth** — role-based (admin / clinician / patient), OAuth (Google, Apple), invite system, rate limiting.

**Observability** — every LLM call traced via Langfuse. Prompt management, quality auditing, and conversation replay.

## Architecture

```
talker/
  agents/           # Orchestrator, screener, conversation, safety monitor, voice mapper
  services/         # LLM, voice, RAG, auth, scheduling, trends, tracing
  models/           # SQLAlchemy ORM + Pydantic schemas
  routes/           # FastAPI routes (assess, auth, admin, clinician, history)
  instruments/      # YAML screening definitions (PHQ-9, GAD-7, PCL-5, ASRS)
  knowledge/        # Clinical markdown docs for RAG (depression, anxiety, PTSD, ADHD)
  templates/        # Jinja2 SSR (calming, minimal UI)
  static/           # CSS + voice JS client
tests/              # 119 tests — instruments, agents, services, auth, deployment
docs/
  architecture.md   # Full technical architecture with diagrams
  livekit-receptionist.md  # Dave's task — setup, design, how to run
```

## Tech stack

| Layer | Technology | Why |
|---|---|---|
| Web | FastAPI + Jinja2 SSR | Async-native, simple UI for a tool that should feel calm |
| Agents | PydanticAI | Type-safe agents, tool calling, works with any OpenAI-compatible provider |
| LLM | OpenRouter (Claude, GPT, Llama) / Ollama local fallback | Single API, model switching per use case |
| Voice | faster-whisper + Piper (local) / Deepgram + ElevenLabs (cloud) / LiveKit (rooms) | Three tiers: offline, cloud, real-time |
| Database | PostgreSQL + SQLAlchemy async + pgvector | JSONB flexibility, vector search for RAG |
| Observability | Langfuse | Tracing, prompt management, quality auditing |
| Auth | bcrypt + OAuth (Google/Apple) + role-based access | Multi-user with clinician/patient hierarchy |

## Quick start

```bash
# Prerequisites: Python 3.12+, PostgreSQL, uv (or pip)
uv sync

# Configure
cp .env.example .env
# Edit .env with your API keys (OpenRouter, Langfuse, etc.)

# Database
docker compose up postgres -d
uv run alembic upgrade head

# Run
uv run uvicorn talker.main:app --reload

# Tests
uv run pytest -v
```

Or run everything with Docker:

```bash
docker compose up
```

## Screening instruments

| Instrument | Condition | Items | Scoring |
|---|---|---|---|
| PHQ-9 | Depression | 9 | Sum (0-27), 5 severity tiers |
| GAD-7 | Anxiety | 7 | Sum (0-21), 4 severity tiers |
| PCL-5 | PTSD | 20 | Sum (0-80), threshold + flags |
| ASRS v1.1 | ADHD | 6 | Per-item thresholds |

Adding a new instrument = adding a YAML file. The scoring engine is generic.

## Project status

All four development phases complete:
- **Phase 1** — Core agents, web UI, screening flow, Docker deployment
- **Phase 2** — Voice I/O (WebSocket + STT/TTS), voice features (pitch, jitter, shimmer), RAG system, report generation
- **Phase 3** — Admin panel, local LLM fallback (Ollama), session memory, data export
- **Phase 4** — Multi-user auth, scheduling, longitudinal tracking, deployment hardening

See [`docs/architecture.md`](docs/architecture.md) for the full technical deep-dive with Mermaid diagrams.

## License

MIT
