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

# Download required model files (ONNX turn detector + VAD)
uv run python -m talker.livekit_agent download-files

# Run the agent
uv run python -m talker.livekit_agent start

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
| `LANGFUSE_SECRET_KEY` | No | Enables tracing, prompt management, feedback scores |
| `LANGFUSE_PUBLIC_KEY` | No | Required with secret key |

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
5. **Visitor tracking** (when DB is configured) — silently recognizes returning visitors, greets them by name, remembers who they visited last time
6. **Session end** — user clicks "End session" → feedback widget appears (1-5 stars)

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
- Adapts tone based on voice analysis — if a visitor sounds anxious, the agent is warmer; if they're in a rush, it's efficient
- Remembers returning visitors silently — never says "let me register you"
- Uses natural British English — "lifts" not "elevators", "ground floor" not "first floor"

---

## Web UI features

The receptionist also has a web-based voice interface at `/livekit/voice?persona=receptionist`:

- **Live transcription** — both user and agent speech shown in real-time via `lk.transcription` stream, with segment-based deduplication (no duplicate text as you speak)
- **Demo cheat sheet** — collapsible panel with test phrases, building directory, and features to try
- **End session button** — cleanly disconnects and shows the feedback widget
- **Star rating feedback** — 1-5 stars + optional comment, sent to Langfuse as a score linked to the session trace

### How the voice session connects

```
Browser                          FastAPI App                    LiveKit Cloud
   │                                 │                              │
   ├─POST /api/livekit/token────────►│                              │
   │  {persona: "receptionist"}      │──create_room()──────────────►│
   │                                 │──create_dispatch()──────────►│
   │                                 │──create_trace() → Langfuse   │
   │◄───{token, room, trace_id}──────│                              │
   │                                 │                              │
   ├─connect(token)─────────────────────────────────────────────────►│
   │                                 │         dispatch agent ──────►│ Agent Process
   │◄────────────────────────── audio + transcription ──────────────│
   │                                                                │
   ├─disconnect / "End session"                                     │
   ├─show feedback widget (1-5 stars)                               │
   ├─POST /api/feedback {trace_id, rating} ─────► Langfuse Score    │
```

---

## Prompt management

The receptionist's system prompt can be managed in two ways:

1. **Hardcoded** (default) — `RECEPTIONIST_INSTRUCTIONS` in `personas/receptionist.py`
2. **Langfuse** (when configured) — prompt named `talker-receptionist` fetched at agent init

If Langfuse is configured but the prompt doesn't exist or Langfuse is unreachable, the hardcoded version is used automatically. This means you can:
- Edit the prompt in Langfuse UI → changes take effect on next agent session, no redeploy
- Take Langfuse offline → agent keeps working with the fallback prompt

**To seed prompts in Langfuse:**
```bash
LANGFUSE_SECRET_KEY=... LANGFUSE_PUBLIC_KEY=... python -m scripts.seed_langfuse_prompts
```

---

## Code guide

### Files to read (in this order)

| File | What it does | Lines |
|---|---|---|
| [`talker/personas/receptionist.py`](../talker/personas/receptionist.py) | **The main deliverable.** All 7 tool functions, building directory data, system prompt, and the `ReceptionistAgent` class. Start here. | ~520 |
| [`talker/livekit_agent.py`](../talker/livekit_agent.py) | Agent entrypoint. Persona registry, capability wiring, audio processing pipeline, session setup. Dynamic persona from room name. | ~200 |
| [`talker/routes/livekit.py`](../talker/routes/livekit.py) | Token generation, room creation, agent dispatch, feedback endpoint. Creates Langfuse traces with user info. | ~140 |
| [`talker/capabilities/voice_analysis.py`](../talker/capabilities/voice_analysis.py) | Voice mood inference — extracts pitch/jitter/shimmer from audio, infers mood (6 rules), injects context into LLM. | ~230 |
| [`talker/services/tracing.py`](../talker/services/tracing.py) | Langfuse integration — traces, scores, prompt fetching with fallback. | ~90 |
| [`talker/config.py`](../talker/config.py) | All settings via pydantic-settings. Shows every knob available. | ~95 |

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
    │       └── ReceptionistAgent(Agent)   ← instructions (Langfuse or fallback) + tools
    │
    ├── talker/capabilities/voice_analysis.py
    │       ├── infer_mood()               ← 6 acoustic rules
    │       ├── process_audio()            ← Parselmouth feature extraction
    │       └── get_context_prompt()       ← injects mood into LLM context
    │
    ├── talker/routes/livekit.py
    │       ├── /api/livekit/token         ← creates room + dispatches agent + Langfuse trace
    │       └── /api/feedback              ← receives star ratings → Langfuse scores
    │
    ├── talker/services/tracing.py
    │       ├── get_prompt()               ← Langfuse prompt with fallback
    │       ├── create_trace()             ← user_id, session_id tracking
    │       └── create_score()             ← feedback scores on traces
    │
    └── LiveKit Cloud (STT → LLM → TTS)
            ├── Deepgram Nova-3 (speech-to-text)
            ├── GPT-4.1-mini (reasoning + tool calls)
            └── Cartesia Sonic-3 (text-to-speech)
```

### Design decisions

**Persona as configuration, not code** — the receptionist and assessor share the same agent engine. A persona is: tools + system prompt + capabilities. Adding a new persona = a Python file and a registry entry.

**Tools are plain functions** — each `@function_tool()` is independently testable. The directory lookup doesn't know or care that it's being called by a voice agent. Tests call `tool._func(None, args)` directly.

**Dynamic persona from room name** — room names follow `talker-{persona}-{uuid}`. The agent parses the persona at startup, so one agent process handles all personas. No `--persona` CLI arg needed.

**Explicit dispatch** — the token endpoint creates the room AND dispatches the agent. This ensures the right persona connects and creates the Langfuse trace in the same request.

**Capabilities vs tools** — tools are called by the LLM on demand ("look up Sarah Chen"). Capabilities run automatically on every audio turn and inject context before the LLM responds ("the visitor sounds anxious").

**Langfuse prompts with fallback** — prompts fetched from Langfuse can be edited without redeploy. If Langfuse is unavailable, the hardcoded instructions work as a safety net.

---

## Docker deployment

```bash
# Run everything
docker compose up

# Or deploy to a server (e.g. via Coolify)
git push  # auto-deploy if configured
```

The `docker-compose.yml` runs three services:
- **app** — FastAPI web server (port 8090:8000)
- **agent** — LiveKit agent process (`python -m talker.livekit_agent start`)
- **postgres** — pgvector/pgvector:pg16

Both app and agent share the same env block via YAML anchors. The Dockerfile uses UV for fast builds and `platform: linux/amd64` for prebuilt wheels.

---

## Wider platform

This receptionist is one persona on a platform built for structured voice conversations. The same architecture powers a psychology pre-assessment agent with validated DSM-5 screening questionnaires, LLM-powered follow-up conversations, crisis detection, and clinical reports. See the [main README](../README.md) and [`docs/architecture.md`](architecture.md) for the full picture.
