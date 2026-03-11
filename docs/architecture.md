# Talker — Architecture Document

**Last updated:** 2026-03-11
**Status:** All phases (1-4) complete + LiveKit voice personas + Langfuse observability

## What Is Talker?

A voice-first AI agent platform for structured conversations with real-world purpose. Two personas run on the same engine:

- **Psychology Assessor** — validated DSM-5 screening questionnaires via voice or text, LLM follow-up, crisis detection, clinical reports
- **Shard Receptionist** — voice-based building receptionist with tenant lookup, visitor tracking, weather API, and mood-aware responses

The architecture is persona-driven: swap the prompt and tools, keep everything else.

---

## High-Level Architecture

```mermaid
graph TB
    subgraph "Voice Transports"
        WEB["Web UI<br/>FastAPI + Jinja2"]
        WS["WebSocket Voice<br/>Local STT/TTS"]
        LK["LiveKit Rooms<br/>Cloud STT/LLM/TTS"]
    end

    subgraph "Persona Layer"
        direction TB
        PREG["Persona Registry<br/>livekit_agent.py"]
        subgraph "Personas"
            ASSESS["Psychology Assessor<br/>agents/ + instruments/"]
            RECEP["Shard Receptionist<br/>personas/receptionist.py"]
        end
    end

    subgraph "Shared Agent Engine"
        ORCH["Orchestrator"]
        SCREEN["Screener Agent"]
        CONV["Conversation Agent"]
        SAFETY["Safety Monitor"]
        MAPPER["Voice Answer Mapper"]
    end

    subgraph "Services Layer"
        LLM["LLM Service<br/>OpenRouter / Ollama"]
        TRACE["Langfuse<br/>Tracing + Prompts<br/>+ Costs + Scores"]
        DB["PostgreSQL<br/>+ pgvector"]
        RAG["RAG Service<br/>Embeddings + Search"]
    end

    subgraph "Admin Panel"
        ADMIN["Admin Routes<br/>/admin/*"]
        STATS["Stats + Langfuse<br/>Cost Dashboard"]
        LKADMIN["LiveKit Room<br/>Management"]
    end

    WEB --> ORCH
    WS --> ORCH
    LK --> PREG
    PREG --> ASSESS
    PREG --> RECEP
    ASSESS --> ORCH
    CONV --> LLM
    CONV --> RAG
    LLM --> TRACE
    ORCH --> DB
    ADMIN --> STATS
    ADMIN --> LKADMIN
```

---

## Environment Variables — Complete Reference

Every variable the system reads, grouped by subsystem. All are optional unless marked **required**.

### Core App

| Variable | Default | What it does | When it matters |
|---|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://talker:talker@localhost:5432/talker` | PostgreSQL connection string | Always — sessions, users, visitor tracking, RAG all need it. Without it, only LiveKit agent mode works (stateless) |
| `APP_SECRET_KEY` | `change-me-in-production` | Signs session cookies | Always — used by Starlette SessionMiddleware |
| `BASE_URL` | `http://localhost:8000` | Public URL for OAuth callback URLs | When using Google/Apple OAuth |
| `ALLOWED_HOSTS` | `*` | Comma-separated hostnames for TrustedHostMiddleware | Production — prevents host header attacks |
| `DEBUG` | `false` | Enables debug mode | Development only |

### LLM — OpenRouter (primary)

| Variable | Default | What it does | When it matters |
|---|---|---|---|
| `OPENROUTER_API_KEY` | _(empty)_ | OpenRouter API key | **Required** for text-based assessment. Not needed for LiveKit-only mode (LiveKit uses its own LLM) |
| `OPENROUTER_MODEL_CONVERSATION` | `anthropic/claude-sonnet-4` | Model for follow-up conversations | When running text assessments — uses a capable model for nuanced dialogue |
| `OPENROUTER_MODEL_SCREENER` | `anthropic/claude-haiku-4.5` | Model for triage and voice answer mapping | When triaging symptoms — uses a fast/cheap model for classification tasks |
| `LLM_PROVIDER` | `openrouter` | `openrouter` or `ollama` | Controls which LLM backend the text-based agents use |

### LLM — Ollama (local fallback)

| Variable | Default | What it does | When it matters |
|---|---|---|---|
| `OLLAMA_CHAT_MODEL` | `llama3.2` | Local model name | When `LLM_PROVIDER=ollama` — runs entirely offline |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL | When using Ollama |

### LiveKit (real-time voice)

| Variable | Default | What it does | When it matters |
|---|---|---|---|
| `LIVEKIT_URL` | _(empty)_ | WebSocket URL (`wss://...livekit.cloud`) | **Required** for voice personas. Get from LiveKit Cloud dashboard |
| `LIVEKIT_API_KEY` | _(empty)_ | LiveKit API key | **Required** for voice personas |
| `LIVEKIT_API_SECRET` | _(empty)_ | LiveKit API secret | **Required** for voice personas |
| `LIVEKIT_STT_MODEL` | `deepgram/nova-3:multi` | Speech-to-text model in LiveKit pipeline | Configures which STT the agent uses. Free tier includes Deepgram |
| `LIVEKIT_LLM_MODEL` | `openai/gpt-4.1-mini` | LLM model in LiveKit pipeline | Configures which LLM reasons about tool calls. Separate from OpenRouter |
| `LIVEKIT_TTS_MODEL` | `cartesia/sonic-3:...` | Text-to-speech model in LiveKit pipeline | Configures the voice. Includes voice ID in the model string |
| `CARTESIA_API_KEY` | _(empty)_ | Cartesia TTS API key | Only if using Cartesia outside LiveKit free tier |

### Langfuse (observability + prompt management)

| Variable | Default | What it does | When it matters |
|---|---|---|---|
| `LANGFUSE_SECRET_KEY` | _(empty)_ | Langfuse secret key | Enables: LLM tracing, prompt management, cost tracking, user feedback scores. Without it, everything falls back gracefully |
| `LANGFUSE_PUBLIC_KEY` | _(empty)_ | Langfuse public key | Required with secret key |
| `LANGFUSE_HOST` | `https://cloud.langfuse.com` | Langfuse server URL | Change for self-hosted Langfuse |

**What Langfuse enables when configured:**
- **Tracing** — every LLM call logged with user_id, session_id, agent name
- **Prompt management** — persona instructions fetched from Langfuse (`talker-receptionist`, `talker-assessor`), editable without redeploy, falls back to hardcoded if unavailable
- **Cost tracking** — admin dashboard shows 30-day cost trend, per-model usage breakdown
- **User feedback** — star ratings from end-of-session UI attached as scores to traces

### Voice — WebSocket mode (not LiveKit)

| Variable | Default | What it does | When it matters |
|---|---|---|---|
| `VOICE_PROVIDER` | `local` | `local` or `cloud` | Controls STT/TTS for WebSocket voice mode |
| `VOICE_LOCAL_STT_MODEL` | `base` | Whisper model size | When `VOICE_PROVIDER=local` |
| `VOICE_LOCAL_TTS_MODEL` | `en_US-amy-medium` | Piper TTS voice | When `VOICE_PROVIDER=local` |
| `VOICE_LOCAL_MODELS_DIR` | `models/voice` | Where Piper models are stored | When `VOICE_PROVIDER=local` |
| `DEEPGRAM_API_KEY` | _(empty)_ | Deepgram STT key | When `VOICE_PROVIDER=cloud` |
| `DEEPGRAM_MODEL` | `nova-2` | Deepgram model | When `VOICE_PROVIDER=cloud` |
| `ELEVENLABS_API_KEY` | _(empty)_ | ElevenLabs TTS key | When `VOICE_PROVIDER=cloud` |
| `ELEVENLABS_MODEL` | `eleven_multilingual_v2` | ElevenLabs model | When `VOICE_PROVIDER=cloud` |
| `ELEVENLABS_VOICE_ID` | _(empty)_ | ElevenLabs voice | When `VOICE_PROVIDER=cloud` |

### RAG / Embeddings

| Variable | Default | What it does | When it matters |
|---|---|---|---|
| `EMBEDDING_PROVIDER` | `openai` | `openai` or `ollama` | Controls embedding model for RAG |
| `OPENAI_API_KEY` | _(empty)_ | OpenAI API key (embeddings only) | When `EMBEDDING_PROVIDER=openai` — used for text-embedding-3-small, not for chat |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI embedding model | When `EMBEDDING_PROVIDER=openai` |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Ollama embedding model | When `EMBEDDING_PROVIDER=ollama` |
| `RAG_CHUNK_SIZE` | `512` | Characters per knowledge chunk | Affects retrieval granularity |
| `RAG_CHUNK_OVERLAP` | `64` | Overlap between chunks | Prevents context loss at boundaries |
| `RAG_TOP_K` | `5` | Number of chunks retrieved | More = more context but higher token cost |

### Auth

| Variable | Default | What it does | When it matters |
|---|---|---|---|
| `ADMIN_EMAIL` | _(empty)_ | Bootstrap admin user on first startup | First run only — creates admin account |
| `ADMIN_PASSWORD` | _(empty)_ | Admin password | For admin login |
| `GOOGLE_CLIENT_ID` | _(empty)_ | Google OAuth client ID | When enabling Google sign-in |
| `GOOGLE_CLIENT_SECRET` | _(empty)_ | Google OAuth secret | When enabling Google sign-in |
| `APPLE_CLIENT_ID` | _(empty)_ | Apple OAuth client ID | When enabling Apple sign-in |
| `APPLE_CLIENT_SECRET` | _(empty)_ | Apple OAuth secret | When enabling Apple sign-in |

### External APIs

| Variable | Default | What it does | When it matters |
|---|---|---|---|
| `OPENWEATHERMAP_API_KEY` | _(empty)_ | Real London weather data | Receptionist persona — falls back to mock weather if not set |

---

## Persona System

The platform supports multiple personas running on the same engine. Each persona is: **tools + system prompt + capabilities**.

```mermaid
graph TB
    subgraph "What a Persona IS"
        direction LR
        INST["Instructions<br/>(Langfuse with fallback)"]
        TOOLS_P["Tool Registry<br/>(@function_tool functions)"]
        CLASS["Agent Class<br/>extends livekit Agent"]
    end

    subgraph "What a Persona SHARES"
        direction LR
        ENGINE["Voice Pipeline<br/>STT → LLM → TTS"]
        CONFIG_S["Config System<br/>pydantic-settings"]
        TRACE_S["Langfuse<br/>Tracing + Prompts + Scores"]
        AUTH_S["Auth + Roles<br/>gated by persona"]
    end
```

### Current personas

| Persona | Slug | Auth required | Tools | Capabilities | Transport |
|---|---|---|---|---|---|
| Shard Receptionist | `receptionist` | No | 7 (directory, weather, visitor tracking) | Voice analysis | LiveKit |
| Receptionist (basic) | `receptionist-basic` | No | 7 | None | LiveKit |
| Psychology Assessor | `assessor` | Yes | 9 (screening, triage, safety) | Voice analysis | LiveKit + WebSocket + Web |
| Assessor (basic) | `assessor-basic` | Yes | 9 | None | LiveKit |

### Adding a new persona

1. Create `talker/personas/your_persona.py` with `@function_tool` functions
2. Write instructions string (or create in Langfuse as `talker-your-persona`)
3. Create `YourAgent(Agent)` with tools + instructions
4. Register in `PERSONAS` dict in `livekit_agent.py`
5. Write tests

No schema changes, no route changes, no migrations.

---

## Langfuse Integration — Tracing, Prompts, Costs, Feedback

```mermaid
graph TB
    subgraph "Runtime"
        PERSONA["Persona init"] -->|get_prompt| LF_PROMPT["Langfuse Prompts<br/>talker-receptionist<br/>talker-assessor"]
        LF_PROMPT -->|fallback| HARDCODED["Hardcoded instructions"]
        SESSION["Agent session"] -->|create_trace| LF_TRACE["Langfuse Trace<br/>user_id, session_id,<br/>agent_name"]
    end

    subgraph "End of Session"
        UI["Star rating widget"] -->|POST /api/feedback| SCORE["Langfuse Score<br/>user-feedback (0-1)<br/>linked to trace"]
    end

    subgraph "Admin Dashboard"
        ADMIN_STATS["/admin/stats"] -->|API call| LF_API["Langfuse API<br/>/api/public/metrics/daily"]
        LF_API --> COST["Cost trend chart<br/>Model usage table<br/>Trace + observation counts"]
    end
```

**Prompt management flow:**
1. On agent init, `get_prompt("talker-receptionist", RECEPTIONIST_INSTRUCTIONS)` is called
2. If Langfuse is configured and the prompt exists → fetches production version
3. If Langfuse is down or prompt doesn't exist → uses hardcoded fallback
4. Edit prompts in Langfuse UI without redeploying

**Seeding prompts:**
```bash
python -m scripts.seed_langfuse_prompts
```
Creates `talker-receptionist` and `talker-assessor` with production labels. Skips if they already exist.

---

## LiveKit Voice Session — End to End

```mermaid
sequenceDiagram
    participant U as Browser
    participant APP as FastAPI App
    participant LK as LiveKit Cloud
    participant AGT as Agent Process
    participant LF as Langfuse

    U->>APP: POST /api/livekit/token {persona: "receptionist"}
    APP->>LK: create_room("talker-receptionist-abc123")
    APP->>LK: create_dispatch(room, agent_name="talker")
    APP->>LF: create_trace(session_id, user_id, agent_name)
    APP-->>U: {token, room, trace_id}

    U->>LK: connect(token)
    LK->>AGT: dispatch agent to room
    AGT->>AGT: _persona_from_room() → "receptionist"
    AGT->>AGT: _build_agent() + wire capabilities
    AGT->>U: greeting (audio + transcription stream)

    loop Conversation
        U->>LK: audio (WebRTC)
        LK->>AGT: STT transcript
        AGT->>AGT: tool calls (lookup, weather, etc.)
        AGT->>U: TTS audio + lk.transcription stream
    end

    U->>U: disconnect / "End session" button
    U->>U: show feedback widget (1-5 stars)
    U->>APP: POST /api/feedback {trace_id, rating, comment}
    APP->>LF: create_score(trace_id, value, comment)
```

---

## Docker Deployment

Three-service setup via `docker-compose.yml`:

```mermaid
graph LR
    subgraph "Docker Compose"
        APP["app<br/>FastAPI + Uvicorn<br/>port 8090:8000"]
        AGENT["agent<br/>LiveKit agent process<br/>python -m talker.livekit_agent start"]
        PG["postgres<br/>pgvector/pgvector:pg16<br/>port 5432"]
    end

    APP --> PG
    AGENT --> PG
    APP -->|creates rooms + dispatches| LK["LiveKit Cloud"]
    AGENT -->|connects to rooms| LK
```

**Key Dockerfile features:**
- UV package manager for fast dependency installation
- `platform: linux/amd64` for prebuilt wheels (no compile step)
- `--proxy-headers --forwarded-allow-ips *` for correct HTTPS behind reverse proxy
- Agent download-files step bakes ONNX turn detection model into image

**Shared env via YAML anchors:** Both `app` and `agent` services share the same env block (`x-shared-env: &shared-env`), keeping all config DRY.

---

## Admin Dashboard

```mermaid
graph LR
    subgraph "Admin Pages"
        SESSIONS["/admin/<br/>Session list + filters"]
        DETAIL["/admin/sessions/{id}<br/>Full transcript + notes"]
        SAFETY["/admin/safety<br/>Safety events log"]
        STATS["/admin/stats<br/>System stats +<br/>Langfuse cost dashboard"]
        KNOWLEDGE["/admin/knowledge<br/>RAG docs + re-ingest"]
        LIVEKIT["/admin/livekit<br/>Active rooms + close"]
    end

    STATS -->|link| LANGFUSE["Open Langfuse ↗"]
    LIVEKIT -->|link| LKCLOUD["Open LiveKit Cloud ↗"]
```

**Stats page includes:**
- Session counts, completion rate, safety events
- Sessions by state chart
- Average scores by instrument
- Langfuse metrics (when configured): total cost, traces, observations, daily cost trend, per-model usage

---

## Session State Machine (Psychology Assessor)

```mermaid
stateDiagram-v2
    [*] --> CREATED
    CREATED --> INTAKE: start()
    INTAKE --> SCREENING: select_instruments()
    SCREENING --> SCREENING: next instrument
    SCREENING --> FOLLOW_UP: all instruments done
    FOLLOW_UP --> SUMMARY: finish conversation
    SUMMARY --> COMPLETED: generate report + feedback

    INTAKE --> INTERRUPTED_BY_SAFETY: crisis detected
    SCREENING --> INTERRUPTED_BY_SAFETY: crisis detected
    FOLLOW_UP --> INTERRUPTED_BY_SAFETY: crisis detected
```

The receptionist has no formal state machine — it follows an implicit flow driven by the LLM and tool calls.

---

## Safety System

```mermaid
flowchart TB
    INPUT["User message"] --> MONITOR["SafetyMonitor.check()"]
    MONITOR -->|no match| SAFE["Continue normally"]
    MONITOR -->|pattern match| INTERRUPT["SafetyInterrupt"]
    INTERRUPT --> RESOURCES["Crisis resources:<br/>988 Lifeline<br/>Crisis Text Line<br/>IASP<br/>911"]
    INTERRUPT --> LOG["Log safety event"]
```

10 regex patterns covering suicidal ideation, self-harm, and harm to others. Zero latency, zero cost, deterministic. Runs on every user message.

---

## Voice Transport Comparison

| Feature | Local WebSocket | Cloud WebSocket | LiveKit Rooms |
|---|---|---|---|
| STT | faster-whisper (CPU) | Deepgram Nova-2 | Deepgram Nova-3 |
| LLM | OpenRouter / Ollama | OpenRouter / Ollama | GPT-4.1-mini (via LiveKit) |
| TTS | Piper (local neural) | ElevenLabs | Cartesia Sonic-3 |
| API keys needed | None (fully offline) | Deepgram + ElevenLabs | LiveKit only (free tier) |
| Use case | Self-hosted, offline | Production web app | Real-time rooms, playground |
| Latency | ~2s (CPU STT) | ~500ms | ~300ms |

---

## Project Structure

```
talker/
  main.py              # FastAPI app, lifespan, middleware
  livekit_agent.py      # LiveKit agent entrypoint, persona registry
  config.py             # pydantic-settings (all env vars)
  personas/
    receptionist.py     # Shard receptionist: 7 tools, directory, visitor tracking
    assessor.py         # Psychology assessor: 9 tools, screening orchestration
  agents/               # Orchestrator, screener, conversation, safety, voice mapper
  capabilities/
    base.py             # Capability ABC
    voice_analysis.py   # Mood inference from audio (6 rules)
  services/
    tracing.py          # Langfuse: init, traces, scores, prompt fetching
    llm.py              # OpenRouter + Ollama model creation
    database.py         # SQLAlchemy async session factory
    session_repo.py     # Session CRUD
    visitor_repo.py     # Visitor tracking (receptionist)
    embeddings.py       # OpenAI / Ollama embeddings
    rag.py              # pgvector retrieval
    admin_repo.py       # Admin queries (stats, safety events)
    export.py           # JSON + CSV export
  models/
    db.py               # SQLAlchemy ORM (User, Session, Visitor, etc.)
    schemas.py          # Pydantic models
    knowledge.py        # pgvector models
  routes/
    assess.py           # /assess/* — screening + conversation
    voice.py            # /ws/voice — WebSocket voice
    livekit.py          # /api/livekit/token, /api/feedback, /livekit/voice
    admin.py            # /admin/* — dashboard, stats, LiveKit management
    auth.py             # /auth/* — login, OAuth, registration
    history.py          # /history/* — past sessions
  instruments/          # YAML screening definitions (PHQ-9, GAD-7, PCL-5, ASRS)
  knowledge/            # Clinical markdown docs for RAG
  templates/            # Jinja2 (base, assess_*, livekit_voice, admin/*)
  static/               # CSS + JS
scripts/
  seed_langfuse_prompts.py  # Create prompts in Langfuse
tests/                  # 201 tests
docs/
  architecture.md       # This file
  livekit-receptionist.md   # Dave's task — setup, design, how to run
  livekit-architecture.md   # LiveKit integration deep dive
```

---

## Technology Choices

| Technology | Role | Why |
|---|---|---|
| **FastAPI** | Web framework | Async-native, Pydantic-first |
| **Jinja2 SSR** | Templating | Calm UI, no JS framework complexity |
| **PydanticAI** | Agent framework | Type-safe agents with tool calling |
| **OpenRouter** | LLM provider | Single API for Claude, GPT, Llama; model switching per role |
| **Ollama** | LLM fallback | Fully offline when no API key |
| **LiveKit Agents** | Real-time voice | Room-based, managed STT/LLM/TTS, persona dispatch |
| **Langfuse** | Observability | Tracing, prompt management, cost tracking, user feedback scores |
| **PostgreSQL + pgvector** | Storage | JSONB flexibility + vector search for RAG |
| **UV** | Package manager | Fast installs, Docker build speed |
| **Parselmouth** | Voice analysis | Pitch, jitter, shimmer extraction for mood inference |

---

## Key Design Decisions

1. **Persona as configuration, not code** — tools + prompt + capabilities. Adding a persona = a Python file
2. **Langfuse prompts with fallback** — edit prompts without redeploy, but hardcoded defaults ensure the system works without Langfuse
3. **Dynamic persona from room name** — `talker-{persona}-{uuid}` parsed at agent startup, no CLI args needed
4. **Explicit agent dispatch** — token endpoint creates room + dispatches agent (not auto-dispatch), ensuring the right persona connects
5. **User feedback linked to traces** — star ratings sent to Langfuse as scores, enabling prompt quality measurement per-persona
6. **Safety via regex first** — zero latency, zero cost, deterministic crisis detection on every message
7. **YAML-driven instruments** — adding a screening questionnaire = adding a YAML file, no code
8. **Three voice tiers** — offline (local), cloud (Deepgram+ElevenLabs), real-time (LiveKit) — same agent logic, different transport
