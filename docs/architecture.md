# Talker — Architecture Document

**Last updated:** 2026-03-11
**Status:** Phase 1 MVP + DB persistence + Voice I/O implemented, Phases 2-4 planned

## What Is Talker?

A psychology pre-assessment voice assistant. Users take validated DSM-5 screening questionnaires via voice or text, followed by a conversational follow-up, to understand their symptoms and know where to seek professional help.

**It is NOT a medical tool.** It is a guide.

---

## High-Level Architecture

```mermaid
graph TB
    subgraph "User Interface"
        WEB["Web UI<br/>FastAPI + Jinja2"]
        VOICE["Voice I/O<br/>WebSocket + STT/TTS"]
    end

    subgraph "Agent Layer"
        ORCH["Orchestrator"]
        SCREEN["Screener Agent"]
        CONV["Conversation Agent"]
        SAFETY["Safety Monitor"]
        MAPPER["Voice Answer Mapper"]
    end

    subgraph "Services Layer"
        LLM["LLM Service<br/>OpenRouter + PydanticAI"]
        TRACE["Tracing<br/>Langfuse"]
        INSTR["Instrument Loader<br/>YAML-driven"]
        DB["Database<br/>PostgreSQL + SQLAlchemy"]
        TOOLS["Agent Tools<br/>Triage, Scoring"]
        VPROV["Voice Provider<br/>Local or Cloud"]
        VFEAT["Voice Features<br/>Parselmouth"]
    end

    WEB --> ORCH
    VOICE --> ORCH
    ORCH --> SCREEN
    ORCH --> CONV
    ORCH --> SAFETY
    ORCH --> TOOLS
    SCREEN --> INSTR
    CONV --> LLM
    LLM --> TRACE
    ORCH --> DB
    VOICE --> VPROV
    VOICE --> VFEAT
    VOICE --> MAPPER
    MAPPER --> LLM
```

**Why this architecture?**
The hybrid screening model (rigid questionnaires + open conversation) maps naturally to specialized agents. The Orchestrator decides when to use structured screeners vs free-form dialogue. Adding a new screening instrument = adding a YAML file, not writing code.

---

## Session State Machine

```mermaid
stateDiagram-v2
    [*] --> CREATED
    CREATED --> INTAKE: start()
    INTAKE --> SCREENING: select_instruments()
    SCREENING --> SCREENING: next instrument
    SCREENING --> FOLLOW_UP: all instruments done
    FOLLOW_UP --> SUMMARY: skip or finish conversation
    SUMMARY --> COMPLETED: generate report

    INTAKE --> INTERRUPTED_BY_SAFETY: crisis detected
    SCREENING --> INTERRUPTED_BY_SAFETY: crisis detected
    FOLLOW_UP --> INTERRUPTED_BY_SAFETY: crisis detected
    INTERRUPTED_BY_SAFETY --> COMPLETED: after resources provided

    INTAKE --> ABANDONED: timeout/disconnect
    SCREENING --> ABANDONED: timeout/disconnect
    FOLLOW_UP --> ABANDONED: timeout/disconnect
```

**Why a state machine?**
Assessment flow is linear and auditable. Each state has clear entry/exit conditions. Sessions can be persisted mid-flow and resumed. The state is the single source of truth for "where are we."

---

## Agent Layer — How They Work Together

```mermaid
sequenceDiagram
    participant U as User
    participant O as Orchestrator
    participant SM as Safety Monitor
    participant S as Screener Agent
    participant C as Conversation Agent
    participant LLM as LLM (OpenRouter)

    U->>O: Start assessment
    O->>U: Greeting + disclaimers
    U->>O: "I've been anxious and can't sleep"
    O->>SM: check("I've been anxious...")
    SM-->>O: null (safe)
    O->>LLM: Triage — which instruments?
    LLM-->>O: ["phq-9", "gad-7"]
    O->>S: start_instrument("phq-9")

    loop Each question
        S->>U: "Over the last 2 weeks..."
        U->>S: answer (0-3)
        S->>SM: check(user text)
    end

    S-->>O: ScreeningResult{score, severity}
    O->>S: start_instrument("gad-7")
    Note over S,U: Repeat for GAD-7

    O->>C: build_system_prompt(results)
    C->>LLM: Explore flagged areas
    LLM-->>C: Follow-up question
    C->>U: "Can you tell me more about..."

    loop Conversation turns
        U->>C: response
        C->>SM: check(response)
        C->>LLM: Continue conversation
        LLM-->>C: Response
        C->>U: Next question
    end

    O->>U: Summary + recommendations
```

**Why separate agents instead of one monolith?**
- **Screener** asks questions *exactly as validated* — no LLM rephrasing allowed (clinical validity)
- **Conversation** is LLM-powered and exploratory — completely different behavior
- **Safety Monitor** watches everything in parallel — can interrupt any agent at any point
- Each agent is independently testable

---

## Data Flow — Screening Instruments

```mermaid
flowchart LR
    YAML["YAML Definition<br/>phq-9.yaml"] --> LOADER["InstrumentLoader<br/>load() / load_all()"]
    LOADER --> DEF["InstrumentDefinition<br/>questions, options, scoring"]
    DEF --> SCREENER["ScreenerAgent<br/>question-by-question"]
    SCREENER --> ANSWERS["Raw Answers<br/>{q1: 2, q2: 1, ...}"]
    ANSWERS --> SCORE["score() method<br/>sum / custom"]
    SCORE --> RESULT["ScreeningResult<br/>score, severity, flags"]
    RESULT --> ORCH["Orchestrator<br/>completed_results[]"]
```

**Why YAML-driven instruments?**
- Adding PHQ-9, GAD-7, PCL-5, ASRS required zero Python code per instrument
- Each YAML defines: questions, response options, scoring method, severity thresholds, flag rules
- Supports multiple scoring methods (`sum`, `asrs_screener` with per-item thresholds)
- Clinicians can review/edit instruments without touching code

---

## Project Structure

```mermaid
graph LR
    subgraph "talker/ (Python package)"
        direction TB
        MAIN["main.py<br/>FastAPI app, lifespan"]
        CONFIG["config.py<br/>pydantic-settings"]

        subgraph agents/
            ORCH_F["orchestrator.py"]
            SCREEN_F["screener.py"]
            CONV_F["conversation.py"]
            SAFETY_F["safety.py"]
            TOOLS_F["tools.py"]
            VMAP_F["voice_mapper.py"]
        end

        subgraph services/
            LLM_F["llm.py"]
            TRACE_F["tracing.py"]
            INSTR_F["instruments.py"]
            DB_F["database.py"]
            REPO_F["session_repo.py"]
            VOICE_F["voice.py"]
            VFEAT_F["voice_features.py"]
        end

        subgraph models/
            SCHEMA_F["schemas.py<br/>Pydantic models"]
            ORM_F["db.py<br/>SQLAlchemy ORM"]
        end

        subgraph routes/
            MAIN_R["main.py → /"]
            ASSESS_R["assess.py → /assess/*"]
            VOICE_R["voice.py → /assess/voice, /ws/voice"]
            HIST_R["history.py → /history/*"]
            SET_R["settings.py → /settings"]
            REPORT_R["report.py → /report/*"]
        end

        subgraph "templates/ + static/"
            TPL["Jinja2 templates<br/>base, index, assess_*,<br/>history, settings, report"]
            CSS["style.css<br/>calming design"]
            JS["voice.js + audio-processor.js<br/>WebSocket voice client"]
        end

        subgraph instruments/
            PHQ["phq-9.yaml"]
            GAD["gad-7.yaml"]
            PCL["pcl-5.yaml"]
            ASRS["asrs.yaml"]
        end
    end
```

---

## Technology Choices — Why Each One

| Technology | Role | Why chosen |
|---|---|---|
| **FastAPI** | Web framework | Async-native, Pydantic-first, great for both REST APIs and SSR with Jinja2 |
| **Jinja2 (SSR)** | Templating | Server-side rendered = simple, no JS framework complexity. Works offline. Mental health tool should feel calm, not "app-like" |
| **PydanticAI** | Agent framework | Type-safe agents with `deps_type`/`output_type`, built-in tool calling, works with any OpenAI-compatible provider |
| **OpenRouter** | LLM provider | Access to Claude, GPT, Llama etc via single API. Easy model switching for conversation vs screener (different cost/quality tradeoffs) |
| **Langfuse** | LLM tracing | Trace every LLM call for quality auditing. Critical for a health-adjacent tool — need to verify conversation quality |
| **PostgreSQL** | Storage | JSONB for flexible schema (raw answers, observations). pgvector extension ready for Phase 2 RAG |
| **SQLAlchemy 2.0 async** | ORM | Async support, mapped columns, works well with FastAPI's async lifecycle |
| **pydantic-settings** | Configuration | Type-safe `.env` loading, validation, defaults. No stringly-typed config |
| **YAML instruments** | Screening definitions | Human-readable, clinician-editable, data-driven. No code per instrument |
| **faster-whisper** | Local STT | Fast CPU inference (int8), lazy-loaded, multiple model sizes |
| **Piper TTS** | Local TTS | Lightweight neural TTS, streaming PCM output, multiple voices |
| **Deepgram** | Cloud STT | High-accuracy speech recognition, Nova-2 model |
| **ElevenLabs** | Cloud TTS | Natural-sounding voices, streaming PCM output |
| **Parselmouth** | Voice analysis | Praat wrapper for pitch (F0), jitter, shimmer, HNR extraction |
| **WeasyPrint** | PDF reports | HTML-to-PDF with CSS support, standalone report templates |

---

## What Is Implemented (Phase 1 MVP)

```mermaid
graph TB
    subgraph "✅ DONE — Phase 1"
        P1_1["Project setup + config"]
        P1_2["Database models + Alembic"]
        P1_3["4 screening instruments<br/>PHQ-9, GAD-7, PCL-5, ASRS"]
        P1_4["LLM service (OpenRouter)"]
        P1_5["Langfuse tracing"]
        P1_6["Safety Monitor<br/>10 crisis regex patterns"]
        P1_7["Screener Agent<br/>question-by-question flow"]
        P1_8["Conversation Agent<br/>LLM-powered follow-up"]
        P1_9["Orchestrator<br/>stateless, DB-backed"]
        P1_10["Tool-calling<br/>triage, score context"]
        P1_11["Web UI<br/>full assessment flow"]
        P1_12["History + Settings pages"]
        P1_13["DB persistence<br/>PostgreSQL + SessionRepository"]
        P1_14["Docker Compose<br/>app + PostgreSQL"]
        P1_15["Report generation<br/>PDF/HTML via WeasyPrint"]
        P1_16["Voice I/O<br/>WebSocket + STT/TTS<br/>Local + Cloud providers"]
        P1_17["Voice features<br/>Pitch, jitter, shimmer, HNR"]
        P1_18["Voice answer mapping<br/>LLM natural language → scale values"]
    end

    subgraph "⬜ NOT YET — Phase 2"
        P2_2["RAG system<br/>pgvector embeddings + clinical knowledge"]
    end

    subgraph "⬜ NOT YET — Phase 3"
        P3_1["Admin panel<br/>audit sessions, safety events"]
        P3_2["Local LLM fallback<br/>Ollama integration"]
        P3_3["Session memory<br/>cross-session context"]
        P3_4["Export/import data"]
    end

    subgraph "⬜ NOT YET — Phase 4"
        P4_1["Multi-user auth"]
        P4_2["Scheduling + reminders"]
        P4_3["Longitudinal tracking<br/>symptom trends over time"]
        P4_4["Public deployment prep"]
    end

    style P1_1 fill:#d4edda
    style P1_2 fill:#d4edda
    style P1_3 fill:#d4edda
    style P1_4 fill:#d4edda
    style P1_5 fill:#d4edda
    style P1_6 fill:#d4edda
    style P1_7 fill:#d4edda
    style P1_8 fill:#d4edda
    style P1_9 fill:#d4edda
    style P1_10 fill:#d4edda
    style P1_11 fill:#d4edda
    style P1_12 fill:#d4edda
    style P1_13 fill:#d4edda
    style P1_14 fill:#d4edda
    style P1_15 fill:#d4edda
    style P1_16 fill:#d4edda
    style P1_17 fill:#d4edda
    style P1_18 fill:#d4edda
```

### Phase 1 — What works today

| Component | Status | Tests | Notes |
|---|---|---|---|
| Config (pydantic-settings) | ✅ | — | `.env` loading, all keys with defaults |
| Pydantic schemas | ✅ | 4 | SessionState, ScreeningResult, etc |
| SQLAlchemy ORM | ✅ | — | User, Session, Screening, Conversation, SafetyEvent tables |
| Alembic migrations | ✅ | — | Initial migration generated |
| Instrument loader | ✅ | 5 | YAML parsing, scoring (sum + asrs_screener), flag rules |
| PHQ-9, GAD-7, PCL-5, ASRS | ✅ | — | Complete YAML definitions |
| LLM service | ✅ | 2 | OpenRouter via PydanticAI |
| Langfuse tracing | ✅ | — | Init, trace creation (no-op when unconfigured) |
| Safety Monitor | ✅ | 6 | 10 crisis patterns, case-insensitive, 4 resource links |
| Screener Agent | ✅ | 5 | Question-by-question, scoring, progress tracking |
| Conversation Agent | ✅ | 3 | System prompt builder with screening context |
| Orchestrator | ✅ | 7 | Stateless, DB-backed, replays answers to restore position |
| Agent tools | ✅ | 5 | parse_instrument_selection, get_score_context, build_triage_prompt |
| SessionRepository | ✅ | 10 | Full async CRUD: create, load, save answers/screenings/messages/summary |
| Web UI (home) | ✅ | — | Calming design, SSR |
| Web UI (assessment) | ✅ | — | Instrument selection → screening → conversation → summary |
| Web UI (history) | ✅ | — | DB-backed session list + detail views |
| Web UI (settings) | ✅ | — | Service status + voice config display |
| Docker Compose | ✅ | — | App + PostgreSQL, auto-migrations on startup |
| Report generation | ✅ | 8 | PDF/HTML via WeasyPrint, download from summary + history |
| Voice providers | ✅ | 6 | Local (faster-whisper + Piper) and cloud (Deepgram + ElevenLabs) |
| Voice features | ✅ | 6 | Pitch, jitter, shimmer, HNR, intensity, speech rate via Parselmouth |
| Voice answer mapper | ✅ | 4 | LLM-powered natural language → screening scale value mapping |
| Voice WebSocket | ✅ | — | Full voice assessment flow (screening + conversation) |
| Voice UI | ✅ | — | Dedicated voice page with mic capture, transcript, TTS playback |
| **Total tests** | | **71** | All passing, ruff clean |

### Phase 1 — Known limitations

- **Conversation falls back to static response** when `OPENROUTER_API_KEY` is not set
- **Voice answer mapping falls back to low confidence** when `OPENROUTER_API_KEY` is not set

---

## Web UI — Assessment Flow

```mermaid
flowchart TB
    HOME["/ Home<br/>Welcome + Begin Assessment"] --> ASSESS["/assess<br/>Select instruments<br/>or Full Checkup"]
    ASSESS -->|POST /assess/start| SCREEN["/assess/screening<br/>Question + progress bar<br/>+ response buttons"]
    ASSESS -->|POST /assess/start voice=1| VOICEUI["/assess/voice<br/>WebSocket voice<br/>screening + conversation"]
    SCREEN -->|POST /assess/answer| SCREEN
    SCREEN -->|all done| CHAT["/assess/conversation<br/>Chat with LLM<br/>+ safety checking"]
    CHAT -->|POST /assess/chat| CHAT
    CHAT -->|Skip to Summary| SUMMARY["/assess/summary<br/>Scores + severity<br/>+ recommendations"]
    VOICEUI -->|Skip to Summary| SUMMARY
    VOICEUI -->|Switch to text| SCREEN
    SUMMARY --> HOME

    HIST["/history<br/>Past sessions"] --> DETAIL["/history/{id}<br/>Session detail"]
    SETTINGS["/settings<br/>Service status<br/>+ model config"]
```

---

## Safety System

```mermaid
flowchart TB
    INPUT["User message"] --> MONITOR["SafetyMonitor.check()"]
    MONITOR -->|no match| SAFE["Continue normally"]
    MONITOR -->|pattern match| INTERRUPT["SafetyInterrupt"]
    INTERRUPT --> RESOURCES["Crisis resources:<br/>988 Lifeline<br/>Crisis Text Line<br/>IASP<br/>911"]
    INTERRUPT --> LOG["Log safety event"]
    RESOURCES --> USER["Show to user immediately"]
```

**10 regex patterns** covering:
- Suicidal ideation ("kill myself", "end my life", "want to die", etc.)
- Self-harm ("cutting myself", "self-harm")
- Harm to others ("want to hurt someone")
- Planning language ("plan to kill/die")

All case-insensitive. The Safety Monitor runs on **every** user message in every state.

**Why regex instead of LLM?**
- Zero latency — critical for safety
- Zero cost — no API calls
- Deterministic — same input always triggers same response
- Works offline — no dependency on external services
- LLM-based safety detection planned as an additional layer in Phase 2

---

## Dependency Graph

```mermaid
graph BT
    CONFIG["config.py"] --> MAIN["main.py"]
    CONFIG --> LLM["services/llm.py"]
    CONFIG --> TRACE["services/tracing.py"]
    CONFIG --> DB_SVC["services/database.py"]

    SCHEMAS["models/schemas.py"] --> SCREENER["agents/screener.py"]
    SCHEMAS --> CONV["agents/conversation.py"]
    SCHEMAS --> ORCH["agents/orchestrator.py"]
    SCHEMAS --> TOOLS["agents/tools.py"]
    SCHEMAS --> DB_MOD["models/db.py"]

    INSTR["services/instruments.py"] --> SCREENER
    INSTR --> TOOLS
    INSTR --> ORCH

    SCREENER --> ORCH
    CONV --> ORCH
    SAFETY["agents/safety.py"] --> ORCH
    TOOLS --> ORCH

    ORCH --> ASSESS_R["routes/assess.py"]
    LLM --> ASSESS_R
    INSTR --> ASSESS_R

    CONFIG --> SETTINGS_R["routes/settings.py"]
    INSTR --> SETTINGS_R

    MAIN --> |include_router| ASSESS_R
    MAIN --> |include_router| MAIN_R["routes/main.py"]
    MAIN --> |include_router| HIST_R["routes/history.py"]
    MAIN --> |include_router| SETTINGS_R
```

---

## Screening Instruments — Current Coverage

```mermaid
graph LR
    subgraph "Implemented"
        PHQ["PHQ-9<br/>Depression<br/>9 items, sum scoring<br/>5 severity tiers"]
        GAD["GAD-7<br/>Anxiety<br/>7 items, sum scoring<br/>4 severity tiers"]
        PCL["PCL-5<br/>PTSD<br/>20 items, sum scoring<br/>2 tiers + flags"]
        ASRS["ASRS v1.1<br/>ADHD<br/>6 items, per-item thresholds"]
    end

    subgraph "Planned (add YAML only)"
        MDQ["MDQ<br/>Bipolar"]
        AUDIT["AUDIT-C<br/>Alcohol"]
        ISI["ISI<br/>Insomnia"]
        PSS["PSS-10<br/>Stress"]
        PHQ15["PHQ-15<br/>Somatic"]
        PC_PTSD["PC-PTSD-5<br/>PTSD Short"]
    end

    style PHQ fill:#d4edda
    style GAD fill:#d4edda
    style PCL fill:#d4edda
    style ASRS fill:#d4edda
```

---

## Phase 2-4 Roadmap

```mermaid
gantt
    title Talker Development Roadmap
    dateFormat YYYY-MM
    section Phase 1 (Done)
        Core agents + Web UI          :done, p1, 2026-03, 2026-03
    section Phase 2 (Next)
        Voice I/O (WebSocket + STT/TTS) :done, p2a, 2026-03, 2026-03
        Voice features (Parselmouth)  :done, p2f, 2026-03, 2026-03
        RAG system (pgvector)         :p2b, 2026-03, 2026-04
        DB persistence                :done, p2d, 2026-03, 2026-03
        Report generation             :done, p2e, 2026-03, 2026-03
    section Phase 3
        Admin panel                   :p3a, 2026-04, 2026-05
        Local LLM (Ollama)            :p3b, 2026-04, 2026-05
        Session memory                :p3c, 2026-05, 2026-05
    section Phase 4
        Multi-user auth               :p4a, 2026-05, 2026-06
        Longitudinal tracking         :p4b, 2026-05, 2026-06
        Public deployment             :p4c, 2026-06, 2026-06
```

---

## Key Design Decisions — Why This Way

### 1. Agent architecture over pipeline or state machine
The hybrid nature of Talker (structured screening → open conversation) requires different behaviors at different times. An orchestrator + specialized agents handles this naturally. A pipeline would struggle with the transition from rigid questionnaires to free-form dialogue. A pure state machine would be too rigid for the conversation phase.

### 2. YAML-driven instruments over code
Clinical screening instruments are standardized — the questions, response options, and scoring are all defined by medical literature. Encoding this as data (YAML) means: no per-instrument code, easy to add new instruments, clinicians can review definitions directly, and the scoring engine is generic and well-tested.

### 3. SSR (Jinja2) over SPA (React/Vue)
For a mental health tool, the UI should feel calm and simple. Server-side rendering means: no JavaScript framework complexity, faster initial loads, works with poor connections, and the UI is a thin layer over the agent logic. If the tool grows to need real-time voice visualization, that's a targeted JS addition, not a full SPA rewrite.

### 4. Safety via regex first, LLM second
Safety detection must be: instant (no API latency), deterministic (same words always trigger), and free (no cost per check). Regex handles the obvious patterns. LLM-based nuanced detection (e.g., "I don't see the point anymore") will be added as an additional layer that enhances, not replaces, the regex baseline.

### 5. OpenRouter over direct API
Single integration point for multiple model providers. Can switch between Claude (quality), GPT (speed), or open models (cost) via config change. The screener uses a cheaper/faster model (Haiku) while conversation uses a more capable one (Sonnet) — different quality needs, same interface.

### 6. Stateless Orchestrator with DB persistence
The Orchestrator holds no mutable state — it loads SessionData from PostgreSQL per request and replays screener answers to restore position. This makes the app fully stateless and horizontally scalable. UUID session IDs prevent enumeration. JSONB columns store flexible data (instrument queues, raw answers) without schema migrations for every field change.

### 7. Pydantic everywhere
`pydantic-settings` for config, Pydantic `BaseModel` for all schemas, PydanticAI for agents, SQLAlchemy with mapped columns. One validation/serialization framework across the entire stack. No data crossing boundaries without type checking.
