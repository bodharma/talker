# Talker — Psychology Pre-Assessment Assistant

**Date:** 2026-03-10
**Status:** Approved

## Overview

Voice-based assistant that helps users pre-assess psychological conditions using validated DSM-5 screening instruments followed by conversational exploration. Not a medical tool — a guide to know where to look and who to see.

**Target:** Personal tool first, designed for general public scalability.

## Architecture: Agent-Based

Central orchestrator coordinates specialized sub-agents. Voice I/O and infrastructure services sit underneath as swappable providers.

### System Layers

1. **Voice I/O Layer** — abstracted behind `VoiceProvider` protocol
   - `LiveKitProvider` — LiveKit Agents SDK, cloud STT/TTS (Deepgram, ElevenLabs or similar)
   - `LocalProvider` — faster-whisper for STT, Piper for TTS
   - Auto-detection with manual override
   - Both implement: `listen() -> AsyncIterator[str]`, `speak(text) -> None`

2. **Agent Layer** — the brain (see Agent Design below)

3. **Infrastructure Layer** — cross-cutting services
   - `LLMService` — OpenRouter (cloud) + Ollama (local), same interface
   - `StorageService` — PostgreSQL via SQLAlchemy async
   - `ScoringService` — generic scorer, reads instrument YAML definitions
   - `ReportService` — PDF/HTML generation (WeasyPrint or similar)
   - `TracingService` — Langfuse integration for all LLM calls
   - `VoiceAnalyticsService` — feature extraction + emotion detection from audio

### Agent Design

**Orchestrator Agent**
- Entry point for every session
- Handles greeting, disclaimers, intake conversation
- Selects screening instruments based on intake or offers "full checkup" mode
- Manages transitions between Screener and Conversation agents
- Produces final summary, triggers report generation

**Screener Agent** (generic, data-driven)
- Loads instrument definition from YAML
- Asks questions exactly as validated (no rephrasing)
- Records answers, computes score via ScoringService
- Returns structured result: `{instrument, score, severity, flagged_items}`
- One config per instrument, no per-instrument code

**Conversation Agent**
- Receives context from screener results (flagged areas, severity)
- Explores duration, triggers, daily life impact, history
- LLM-powered with careful system prompts (exploring, not diagnosing)
- Outputs structured observations for the report

**Safety Monitor** (parallel)
- Watches all agent interactions for crisis indicators
- Suicidal ideation, self-harm, psychosis signals
- Can interrupt any agent to provide crisis resources
- Logs safety events separately for admin audit

### Agent Communication

**Framework:** PydanticAI (or lightweight custom) — agents are Python async functions, not autonomous loops. The Orchestrator calls sub-agents directly via `await`.

**Message protocol:** Agents communicate via typed Pydantic models:
- `AgentRequest` — input context + user message
- `AgentResponse` — response text + structured data + next action hint
- Safety Monitor receives a copy of every `AgentRequest`/`AgentResponse` via an async callback. If it flags a crisis, it raises a `SafetyInterrupt` exception that the Orchestrator catches and handles.

**Concurrency:** One session = one agent chain. No concurrent sessions in MVP. Agent instances are scoped per session.

### Session State Machine

```
CREATED → INTAKE → SCREENING → FOLLOW_UP → SUMMARY → COMPLETED
                       ↑            |
                       └────────────┘  (loop for multiple instruments)
Any state → INTERRUPTED_BY_SAFETY → COMPLETED (after crisis resources provided)
Any state → ABANDONED (user disconnects, timeout)
```

- Sessions are resumable if state is not COMPLETED or ABANDONED
- Report generation is automatic on transition to COMPLETED
- User can skip FOLLOW_UP (go straight from SCREENING to SUMMARY)

### Voice Response Mapping (Screener)

In voice mode, users respond naturally ("yeah, pretty much every day"). The Screener Agent uses an LLM call to map free-form responses to the instrument's discrete scale values:
- System prompt includes the question, the valid response options with values
- LLM returns the matched option + confidence score
- If confidence < threshold, the agent asks the user to clarify
- This mapping step is traced in Langfuse for quality auditing

## Screening Instruments

Data-driven via YAML files. Adding a new instrument = adding a YAML file.

Each instrument definition contains:
- **metadata** — name, target condition, citation, version
- **questions** — ordered, exact validated wording
- **response_options** — scale with numeric values
- **scoring** — total computation, subscales, severity thresholds
- **flags** — items requiring special attention regardless of total score
- **follow_up_hints** — context passed to Conversation Agent

### Initial instrument coverage (comprehensive):
- Depression: PHQ-9 (public domain, 9 items)
- Generalized Anxiety: GAD-7 (public domain, 7 items)
- PTSD: PCL-5 (public domain, 20 items)
- ADHD: ASRS-v1.1 (public domain, 6-item screener)
- Bipolar: MDQ (public domain, 13 items)
- Social Anxiety: SPIN (17 items — verify licensing)
- Autism spectrum: AQ-10 (public domain, 10 items)
- Alcohol use: AUDIT (public domain, 10 items)
- Drug use: DAST-10 (public domain, 10 items)
- Insomnia: ISI (public domain, 7 items)

### Deferred instruments (licensing or voice-feasibility concerns):
- OCD: Y-BOCS — clinician-administered, needs adaptation for self-report
- Borderline traits: MSI-BPD — verify licensing
- Eating disorders: EDE-Q — 28 items, grueling in voice mode; consider shorter screener (SCOFF)
- Dissociation: DIS-Q — 63 items, impractical for voice; consider DES-II (28 items) or A-DES

## Voice Analytics (Phase 2)

> Voice analytics is a separate milestone after the core assessment system is working. Phase 1 stores raw audio (with consent) so analytics can be applied retroactively.

Extracts psychological signal from voice beyond transcript content.

**Features captured:**
- Prosody: pitch (F0), pitch variability, speech rate, pauses, volume
- Vocal quality: jitter, shimmer, breathiness
- Temporal: response latency, pause frequency/duration, speech-to-silence ratio
- Emotion/sentiment: detected from audio signal directly

**Implementation:**
- openSMILE or pyAudioAnalysis for feature extraction
- SpeechBrain or Wav2Vec2 fine-tuned for emotion recognition
- All processing runs locally — no cloud dependency

**Storage tiers (user-selectable):**
1. Full audio + extracted features
2. Features only (no raw audio)
3. No voice storage

**Enables:**
- Mood trajectory tracking across sessions
- Correlation between voice features and screening scores
- Real-time hints to Conversation Agent ("user sounds distressed")
- Admin voice analytics audit view

## Storage

**PostgreSQL** with SQLAlchemy async + Alembic migrations.

### Core tables:
- **users** — optional multi-user support, single default user initially
- **sessions** — each assessment visit: mode, provider, memory_consent, voice_consent
- **session_screenings** — instrument results: score, severity, raw_answers (JSONB), flagged_items
- **session_conversations** — transcript + LLM-extracted observations (JSONB)
- **session_summaries** — final summary text, recommendations, areas to explore
- **reports** — generated report file references
- **voice_segments** — raw audio (encrypted at rest via PostgreSQL pgcrypto + application-level AES-256), linked to session, with consent flag
- **voice_features** — extracted feature vectors per utterance + session aggregates
- **safety_events** — crisis/flag events from Safety Monitor

### Cross-session memory:
- Enabled per session via `memory_consent` flag
- Orchestrator queries prior scores for trends
- Conversation Agent gets high-level context, not full transcripts

## LLM Integration

**OpenRouter** as cloud provider:
- Claude for Conversation Agent (best reasoning)
- Cheaper/faster model for Screener Agent (structured Q&A)
- Model selection configurable per agent

**Ollama** as local fallback:
- Same LLMService interface
- Activates when cloud unavailable or user preference

**Langfuse** for observability:
- All LLM calls traced with session-level grouping
- Cost tracking, latency monitoring, prompt versioning
- Self-hostable — can run locally alongside Ollama

## Web UI

**FastAPI + Jinja2**, server-side rendered. Calming visual design — soft palette, whitespace, clear typography.

### Pages:
- `/` — Dashboard: start assessment, recent sessions, trend sparklines
- `/assess` — Assessment page: voice indicator + live transcript (voice mode), text Q&A (web mode), progress display. WebSocket for real-time voice.
- `/assess/{session_id}` — Completed session review: scores, severity, conversation highlights, voice mood indicators, recommendations
- `/history` — Full session history: filters, score trend charts, voice trend charts
- `/report/{session_id}` — View/download report (HTML + PDF)
- `/settings` — Voice provider, memory consent default, model selection, Langfuse status

### Admin panel (`/admin/*`, auth-protected):
- `/admin/` — System dashboard: total sessions, active users, safety flags, service health
- `/admin/sessions` — All sessions across users, filterable, full detail drill-down
- `/admin/safety` — Safety Monitor audit log
- `/admin/langfuse` — LLM usage overview, links to full Langfuse dashboard
- `/admin/instruments` — Loaded instrument configs, validation status, usage stats
- `/admin/voice-analytics` — Aggregated voice patterns, consent audit, storage usage
- `/admin/users` — User management (future multi-user)

**Auth:** Simple admin token initially. OAuth/SSO when targeting general public.

## Configuration

**pydantic-settings** with `.env` support:
- Database URL
- OpenRouter API key + default models per agent
- Langfuse credentials
- LiveKit connection details
- Local model paths (Whisper, Piper, Ollama)
- Voice analytics settings (storage tier default)
- Admin token

**Pydantic** for all data schemas — API I/O, instrument definitions, agent messages, session data.

## Project Structure

```
talker/
├── main.py                     # FastAPI app entry point
├── config.py                   # pydantic-settings BaseSettings
├── agents/
│   ├── orchestrator.py
│   ├── screener.py
│   ├── conversation.py
│   └── safety.py
├── services/
│   ├── llm.py                  # OpenRouter + Ollama
│   ├── voice.py                # LiveKit + Local providers
│   ├── voice_analytics.py      # Feature extraction + emotion detection
│   ├── scoring.py              # Generic instrument scorer
│   ├── storage.py              # Postgres via SQLAlchemy async
│   ├── report.py               # PDF/HTML generation
│   └── tracing.py              # Langfuse integration
├── instruments/
│   ├── phq-9.yaml
│   ├── gad-7.yaml
│   └── ...
├── models/
│   ├── db.py                   # SQLAlchemy ORM models
│   └── schemas.py              # Pydantic schemas
├── routes/
│   ├── assess.py
│   ├── history.py
│   ├── admin.py
│   └── api.py
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── assess.html
│   ├── session.html
│   ├── history.html
│   ├── report.html
│   ├── settings.html
│   └── admin/
│       ├── dashboard.html
│       ├── sessions.html
│       ├── safety.html
│       ├── instruments.html
│       └── voice_analytics.html
├── static/
│   ├── css/
│   └── js/
├── migrations/                 # Alembic
├── tests/
└── docs/
```

## WebSocket Protocol (Voice Mode)

Messages are JSON with a `type` field:

**Client → Server:**
- `{type: "audio", data: "<base64 PCM>"}` — audio chunk from mic
- `{type: "start"}` — begin listening
- `{type: "stop"}` — stop listening
- `{type: "interrupt"}` — user interrupted the assistant

**Server → Client:**
- `{type: "transcript", text: "...", final: bool}` — STT result (interim or final)
- `{type: "response", text: "...", audio: "<base64>"}` — agent response with TTS audio
- `{type: "state", state: "screening", instrument: "PHQ-9", question: 3, total: 9}` — session state update
- `{type: "safety", message: "...", resources: [...]}` — safety interrupt

## Service Degradation

| Service | Fallback | User notification |
|---------|----------|-------------------|
| OpenRouter down | Switch to Ollama if configured, otherwise text error | "Switching to local mode" / "LLM unavailable" |
| Ollama not configured + OpenRouter down | Text-only web mode with pre-written questions (no conversation agent) | "Voice assistant unavailable, using questionnaire mode" |
| LiveKit disconnects mid-session | Switch to local voice provider, resume session | "Reconnecting locally..." |
| No voice providers available | Web-only text mode | Automatic fallback, no voice UI shown |
| Langfuse down | Continue without tracing, log warning | Silent (admin-visible only) |
| PostgreSQL down | Cannot operate — show maintenance page | "Service temporarily unavailable" |

## Phasing

### Phase 1 — MVP (target: working end-to-end)
- Text-only web mode (no voice yet)
- OpenRouter as sole LLM provider
- 3-4 instruments: PHQ-9, GAD-7, PCL-5, ASRS
- Orchestrator + Screener + basic Conversation Agent
- Safety Monitor (keyword-based, no ML)
- PostgreSQL storage, session history
- Basic Jinja2 UI (assess, history, session review)
- Langfuse tracing
- No admin panel (use Langfuse dashboard directly)

### Phase 2 — Voice
- LiveKit voice provider
- Local voice provider (faster-whisper + Piper)
- WebSocket protocol
- Voice response mapping in Screener
- Raw audio storage with consent

### Phase 3 — Full coverage
- Remaining instruments (10+)
- Ollama local LLM fallback
- Report generation (PDF/HTML)
- Admin panel
- Cross-session memory

### Phase 4 — Voice Analytics
- Feature extraction (openSMILE)
- Emotion detection (pre-trained models, no fine-tuning initially)
- Mood trajectory tracking
- Voice analytics admin view

## Key Disclaimers (shown to every user)

- This is NOT a medical or diagnostic tool
- Results are screening indicators, not diagnoses
- Always consult a qualified mental health professional
- In crisis, contact emergency services or crisis hotline
