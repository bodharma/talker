# Talker — Architecture Document

**Last updated:** 2026-03-11
**Status:** All phases (1-4) complete

## What Is Talker?

A psychology pre-assessment voice assistant. Users take validated DSM-5 screening questionnaires via voice or text, followed by a conversational follow-up, to understand their symptoms and know where to seek professional help.

**It is NOT a medical tool.** It is a guide.

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
        PREG["Persona Registry<br/>livekit_agent.py / orchestrator.py"]
        subgraph "Personas"
            ASSESS["Psychology Assessor<br/>agents/ + instruments/"]
            RECEP["Shard Receptionist<br/>personas/receptionist.py"]
            FUTURE["Future Personas<br/>personas/?.py"]
        end
    end

    subgraph "Shared Agent Engine"
        ORCH["Orchestrator"]
        SCREEN["Screener Agent"]
        CONV["Conversation Agent"]
        SAFETY["Safety Monitor"]
        MAPPER["Voice Answer Mapper"]
    end

    subgraph "Tool Registries"
        ATOOLS["Assessor Tools<br/>triage, scoring, safety"]
        RTOOLS["Receptionist Tools<br/>directory, weather,<br/>building info, visitor log"]
    end

    subgraph "Services Layer"
        LLM["LLM Service<br/>OpenRouter / Ollama"]
        TRACE["Tracing + Prompts<br/>Langfuse"]
        INSTR["Instrument Loader<br/>YAML-driven"]
        DB["Database<br/>PostgreSQL + SQLAlchemy"]
        VPROV["Voice Provider<br/>Local / Cloud / LiveKit"]
        VFEAT["Voice Features<br/>Parselmouth"]
        RAG["RAG Service<br/>pgvector + Embeddings"]
        SMEM["Session Memory<br/>Cross-session context"]
    end

    subgraph "Admin Panel"
        ADMIN["Admin Routes<br/>/admin/*"]
        AREPO["Admin Repository<br/>Stats, Safety, Audit"]
        EXPORT["Export Service<br/>JSON + CSV"]
    end

    WEB --> ORCH
    WS --> ORCH
    LK --> PREG
    PREG --> ASSESS
    PREG --> RECEP
    ASSESS --> ORCH
    ASSESS --> ATOOLS
    RECEP --> RTOOLS
    ORCH --> SCREEN
    ORCH --> CONV
    ORCH --> SAFETY
    SCREEN --> INSTR
    CONV --> LLM
    CONV --> RAG
    CONV --> SMEM
    LLM --> TRACE
    ORCH --> DB
    WS --> VPROV
    WS --> VFEAT
    WS --> MAPPER
    MAPPER --> LLM
    ADMIN --> AREPO
    ADMIN --> EXPORT
    AREPO --> DB
```

**Why this architecture?**
The hybrid screening model (rigid questionnaires + open conversation) maps naturally to specialized agents. The Orchestrator decides when to use structured screeners vs free-form dialogue. Adding a new screening instrument = adding a YAML file, not writing code. Adding a new persona = adding a tool file + registering the agent class.

---

## Persona System — How Different Agents Share One Platform

> **For AI tools:** This section explains the persona abstraction. When adding new personas, follow this pattern exactly.

The platform supports multiple personas — different conversational agents with different tools, instructions, and purposes — running on the same engine. Each persona is a configuration, not a codebase.

```mermaid
graph TB
    subgraph "What a Persona IS"
        direction LR
        INST["Instructions<br/>(system prompt via Langfuse)"]
        TOOLS_P["Tool Registry<br/>(@function_tool functions)"]
        CLASS["Agent Class<br/>extends livekit Agent"]
    end

    subgraph "What a Persona SHARES"
        direction LR
        ENGINE["Voice Pipeline<br/>STT → LLM → TTS"]
        CONFIG_S["Config System<br/>pydantic-settings"]
        TRACE_S["Observability<br/>Langfuse tracing"]
        AUTH_S["Auth + Roles<br/>if using web UI"]
    end

    subgraph "Current Personas"
        direction TB
        PA["🧠 Psychology Assessor<br/>━━━━━━━━━━━━━━━<br/>Tools: triage, screening,<br/>scoring, safety, RAG<br/>Transport: WebSocket + Web UI<br/>Data: YAML instruments,<br/>knowledge base, PostgreSQL"]

        PR["🏢 Shard Receptionist<br/>━━━━━━━━━━━━━━━<br/>Tools: directory lookup,<br/>availability, building info,<br/>weather API, visitor log<br/>Transport: LiveKit rooms<br/>Data: in-memory dicts"]
    end
```

### Persona comparison — same pattern, different purpose

```mermaid
graph LR
    subgraph "Psychology Assessor"
        direction TB
        A_GREET["Greet + disclaimers"]
        A_TRIAGE["Triage: which instruments?"]
        A_SCREEN["Administer screening"]
        A_CONV["Follow-up conversation"]
        A_SUMMARY["Summary + recommendations"]
        A_GREET --> A_TRIAGE --> A_SCREEN --> A_CONV --> A_SUMMARY
    end

    subgraph "Shard Receptionist"
        direction TB
        R_GREET["Greet visitor"]
        R_WHO["Who are you here to see?"]
        R_LOOKUP["Look up in directory"]
        R_AVAIL["Check availability"]
        R_DIRECT["Give directions + log"]
        R_GREET --> R_WHO --> R_LOOKUP --> R_AVAIL --> R_DIRECT
    end
```

Both follow the same pattern: **greet → understand need → use tools → respond naturally → close.**

### Adding a new persona

```mermaid
flowchart LR
    A["1. Create<br/>personas/name.py"] --> B["2. Define tools<br/>@function_tool()"]
    B --> C["3. Write instructions<br/>or fetch from Langfuse"]
    C --> D["4. Create Agent class<br/>tools + instructions"]
    D --> E["5. Register in<br/>PERSONAS dict"]
    E --> F["6. Add tests"]
```

No schema changes. No route changes. No database migrations. Just a Python file with tools and a prompt.

### Capabilities — pluggable pipeline modules

> **For AI tools:** Capabilities and tools are different things. Tools are called by the LLM on demand. Capabilities run automatically on every audio turn and inject context into the LLM before it responds.

Capabilities are processing modules that hook into the voice pipeline. They analyze audio, enrich context, and optionally expose tools. Any persona can opt into any capability.

```mermaid
graph TB
    subgraph "Pipeline Flow"
        direction LR
        AUDIO["Audio turn"] --> CAP["Capabilities<br/>(automatic)"]
        CAP --> CONTEXT["Enriched context"]
        CONTEXT --> LLM["LLM"]
        LLM --> TOOLS["Tools<br/>(on demand)"]
        TOOLS --> RESPONSE["Response"]
    end

    subgraph "Current Capabilities"
        VA["🎙 VoiceAnalysisCapability<br/>━━━━━━━━━━━━━━━<br/>Wraps voice_features.py<br/>Extracts: pitch, jitter, shimmer, HNR<br/>Infers: mood (6 rules)<br/>Exposes: get_voice_analysis, get_voice_trend<br/>Injects: mood context per turn"]
    end

    subgraph "Capability ABC"
        BASE["BaseCapability<br/>━━━━━━━━━━━━━━━<br/>process_audio(audio, sr, transcript)<br/>get_context_prompt(results)<br/>get_tools()"]
    end

    VA --> BASE
```

**Adding a capability to a persona:**

```python
PERSONAS = {
    "receptionist": {
        "agent_class": ReceptionistAgent,
        "capabilities": [VoiceAnalysisCapability],  # plug in
    },
    "receptionist-basic": {
        "agent_class": ReceptionistAgent,
        "capabilities": [],  # opt out
    },
}
```

See [`docs/livekit-architecture.md`](livekit-architecture.md) for the detailed capability architecture with mood inference rules and audio processing pipeline.

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
        LKAGENT["livekit_agent.py<br/>LiveKit entrypoint"]
        CONFIG["config.py<br/>pydantic-settings"]

        subgraph personas/
            REC_P["receptionist.py<br/>Shard receptionist tools + agent"]
        end

        subgraph agents/
            ORCH_F["orchestrator.py"]
            SCREEN_F["screener.py"]
            CONV_F["conversation.py"]
            SAFETY_F["safety.py"]
            TOOLS_F["tools.py"]
            VMAP_F["voice_mapper.py"]
            RAGT_F["rag_tools.py"]
        end

        subgraph services/
            LLM_F["llm.py<br/>OpenRouter + Ollama"]
            TRACE_F["tracing.py"]
            INSTR_F["instruments.py"]
            DB_F["database.py"]
            REPO_F["session_repo.py"]
            VOICE_F["voice.py"]
            VFEAT_F["voice_features.py"]
            EMB_F["embeddings.py"]
            RAG_F["rag.py"]
            ING_F["ingest.py"]
            SMEM_F["session_memory.py"]
            AREP_F["admin_repo.py"]
            EXP_F["export.py"]
        end

        subgraph models/
            SCHEMA_F["schemas.py<br/>Pydantic models"]
            ORM_F["db.py<br/>SQLAlchemy ORM"]
            KNOW_F["knowledge.py<br/>pgvector models"]
        end

        subgraph routes/
            MAIN_R["main.py → /"]
            ASSESS_R["assess.py → /assess/*"]
            VOICE_R["voice.py → /assess/voice, /ws/voice"]
            HIST_R["history.py → /history/*"]
            SET_R["settings.py → /settings"]
            REPORT_R["report.py → /report/*"]
            ADMIN_R["admin.py → /admin/*"]
        end

        subgraph "templates/ + static/"
            TPL["Jinja2 templates<br/>base, index, assess_*,<br/>history, settings, report"]
            ATPL["admin/ templates<br/>login, sessions, detail,<br/>safety, stats, knowledge"]
            CSS["style.css<br/>calming design"]
            JS["voice.js + audio-processor.js<br/>WebSocket voice client"]
        end

        subgraph knowledge/
            CLIN["clinical/<br/>depression, anxiety,<br/>ptsd, adhd, comorbidity"]
            PSYCH["psychoeducation/<br/>instrument guides,<br/>treatment approaches"]
            RES["resources/<br/>crisis, finding therapist"]
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
| **OpenRouter** | LLM provider (cloud) | Access to Claude, GPT, Llama etc via single API. Easy model switching for conversation vs screener (different cost/quality tradeoffs) |
| **Ollama** | LLM provider (local) | Local LLM fallback when no API key configured. Uses OpenAI-compatible endpoint |
| **Langfuse** | LLM tracing | Trace every LLM call for quality auditing. Critical for a health-adjacent tool — need to verify conversation quality |
| **PostgreSQL + pgvector** | Storage + embeddings | JSONB for flexible schema. pgvector for RAG semantic search with cosine distance |
| **Chart.js** | Admin visualizations | Lightweight charting (CDN) for voice features and stats dashboards |
| **SQLAlchemy 2.0 async** | ORM | Async support, mapped columns, works well with FastAPI's async lifecycle |
| **pydantic-settings** | Configuration | Type-safe `.env` loading, validation, defaults. No stringly-typed config |
| **YAML instruments** | Screening definitions | Human-readable, clinician-editable, data-driven. No code per instrument |
| **faster-whisper** | Local STT | Fast CPU inference (int8), lazy-loaded, multiple model sizes |
| **Piper TTS** | Local TTS | Lightweight neural TTS, streaming PCM output, multiple voices |
| **Deepgram** | Cloud STT | High-accuracy speech recognition, Nova-2 model |
| **ElevenLabs** | Cloud TTS | Natural-sounding voices, streaming PCM output |
| **Parselmouth** | Voice analysis | Praat wrapper for pitch (F0), jitter, shimmer, HNR extraction |
| **LiveKit Agents** | Real-time voice transport | Room-based communication, managed STT/LLM/TTS pipeline, persona-driven agents via `@function_tool` |
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

    subgraph "✅ DONE — Phase 2"
        P2_2["RAG system<br/>pgvector embeddings + clinical knowledge"]
    end

    subgraph "✅ DONE — Phase 3"
        P3_1["Admin panel<br/>session audit, safety events,<br/>stats, knowledge mgmt"]
        P3_2["Local LLM fallback<br/>Ollama integration + auto-fallback"]
        P3_3["Session memory<br/>cross-session context"]
        P3_4["Data export<br/>JSON + CSV"]
    end

    subgraph "✅ DONE — Phase 4"
        P4_1["Multi-user auth<br/>roles, OAuth, invites"]
        P4_2["Scheduling + reminders"]
        P4_3["Longitudinal tracking<br/>symptom trends over time"]
        P4_4["Public deployment prep<br/>security headers, rate limiting"]
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
    style P2_2 fill:#d4edda
    style P3_1 fill:#d4edda
    style P3_2 fill:#d4edda
    style P3_3 fill:#d4edda
    style P3_4 fill:#d4edda
    style P4_1 fill:#d4edda
    style P4_2 fill:#d4edda
    style P4_3 fill:#d4edda
    style P4_4 fill:#d4edda
```

### What works today (Phases 1-4)

| Component | Status | Tests | Notes |
|---|---|---|---|
| Config (pydantic-settings) | ✅ | — | `.env` loading, all keys with defaults |
| Pydantic schemas | ✅ | 4 | SessionState, ScreeningResult, etc |
| SQLAlchemy ORM | ✅ | — | User, Session, Screening, Conversation, SafetyEvent, Knowledge tables |
| Alembic migrations | ✅ | — | 3 migrations (initial, knowledge tables, admin_notes) |
| Instrument loader | ✅ | 5 | YAML parsing, scoring (sum + asrs_screener), flag rules |
| PHQ-9, GAD-7, PCL-5, ASRS | ✅ | — | Complete YAML definitions |
| LLM service | ✅ | 6 | OpenRouter + Ollama fallback via PydanticAI |
| Langfuse tracing | ✅ | — | Init, trace creation (no-op when unconfigured) |
| Safety Monitor | ✅ | 6 | 10 crisis patterns, case-insensitive, 4 resource links |
| Screener Agent | ✅ | 5 | Question-by-question, scoring, progress tracking |
| Conversation Agent | ✅ | 3 | System prompt builder with screening + RAG + memory context |
| Orchestrator | ✅ | 7 | Stateless, DB-backed, replays answers to restore position |
| Agent tools | ✅ | 7 | parse_instrument_selection, get_score_context, build_clinical_query |
| SessionRepository | ✅ | 10 | Full async CRUD: create, load, save answers/screenings/messages/summary |
| RAG system | ✅ | 15 | Markdown chunking, embeddings (OpenAI/Ollama), pgvector search |
| Session memory | ✅ | 2 | Cross-session context injection into prompts |
| Admin panel | ✅ | 5 | Session audit, safety dashboard, stats, knowledge mgmt |
| Data export | ✅ | 2 | JSON + CSV export from admin panel |
| Web UI (home) | ✅ | — | Calming design, SSR |
| Web UI (assessment) | ✅ | — | Instrument selection → screening → conversation → summary |
| Web UI (history) | ✅ | — | DB-backed session list + detail views |
| Web UI (settings) | ✅ | — | Service status, LLM provider, RAG, voice config |
| Docker Compose | ✅ | — | App + PostgreSQL, auto-migrations on startup |
| Report generation | ✅ | 8 | PDF/HTML via WeasyPrint, download from summary + history |
| Voice providers | ✅ | 6 | Local (faster-whisper + Piper) and cloud (Deepgram + ElevenLabs) |
| Voice features | ✅ | 6 | Pitch, jitter, shimmer, HNR, intensity, speech rate via Parselmouth |
| Voice answer mapper | ✅ | 4 | LLM-powered natural language → screening scale value mapping |
| Voice WebSocket | ✅ | — | Full voice assessment flow (screening + conversation) |
| Voice UI | ✅ | — | Dedicated voice page with mic capture, transcript, TTS playback |
| Clinical knowledge base | ✅ | — | 12 markdown docs (clinical, psychoeducation, resources) |
| Multi-user auth | ✅ | 10 | Roles (admin/clinician/patient), OAuth (Google/Apple), invites, rate limiting |
| Scheduling | ✅ | 2 | Recurrence (weekly/biweekly/monthly), due tracking |
| Longitudinal trends | ✅ | 1 | Score history, trend direction, Chart.js visualization |
| Deployment prep | ✅ | 3 | Security headers, health endpoint, trusted hosts |
| LiveKit agent | ✅ | — | Persona-driven entrypoint, STT/LLM/TTS pipeline, CLI |
| Receptionist persona | ✅ | 25 | 5 tools, fuzzy matching, directory, weather API |
| Capabilities system | ✅ | 21 | Voice analysis, mood inference (6 rules), trend tracking |
| **Total tests** | | **165** | All passing, ruff clean |

### Known limitations

- **Voice answer mapping falls back to low confidence** when no LLM provider is available
- **pgvector required** for RAG/knowledge features (gracefully skipped when unavailable)

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
    CONFIG --> LK["livekit_agent.py"]
    CONFIG --> REC["personas/receptionist.py"]

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

    REC --> LK
    LK --> |LiveKit SDK| LKCLOUD["LiveKit Cloud"]
```

---

## Voice Transport Comparison

> **For AI tools:** The platform supports three voice transport modes. Each persona can use any transport, but in practice the assessor uses WebSocket and the receptionist uses LiveKit.

```mermaid
graph TB
    subgraph "Transport: Local WebSocket"
        direction LR
        L_STT["faster-whisper<br/>Local CPU inference"]
        L_LLM["OpenRouter / Ollama<br/>via PydanticAI"]
        L_TTS["Piper TTS<br/>Local neural TTS"]
        L_STT --> L_LLM --> L_TTS
    end

    subgraph "Transport: Cloud WebSocket"
        direction LR
        C_STT["Deepgram<br/>Nova-2 cloud STT"]
        C_LLM["OpenRouter / Ollama<br/>via PydanticAI"]
        C_TTS["ElevenLabs<br/>Cloud neural TTS"]
        C_STT --> C_LLM --> C_TTS
    end

    subgraph "Transport: LiveKit Rooms"
        direction LR
        LK_STT["Deepgram<br/>Nova-3 via LiveKit"]
        LK_LLM["OpenAI GPT-4.1-mini<br/>via LiveKit plugin"]
        LK_TTS["Cartesia Sonic-3<br/>via LiveKit plugin"]
        LK_STT --> LK_LLM --> LK_TTS
    end

    subgraph "Use Cases"
        UC_LOCAL["Offline / self-hosted<br/>No API keys needed"]
        UC_CLOUD["Production web app<br/>Best quality"]
        UC_LK["Real-time rooms<br/>LiveKit Playground<br/>Deployable to cloud"]
    end

    L_STT -.-> UC_LOCAL
    C_STT -.-> UC_CLOUD
    LK_STT -.-> UC_LK
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
    section Phase 2 (Done)
        Voice I/O (WebSocket + STT/TTS) :done, p2a, 2026-03, 2026-03
        Voice features (Parselmouth)  :done, p2f, 2026-03, 2026-03
        RAG system (pgvector)         :done, p2b, 2026-03, 2026-03
        DB persistence                :done, p2d, 2026-03, 2026-03
        Report generation             :done, p2e, 2026-03, 2026-03
    section Phase 3 (Done)
        Admin panel                   :done, p3a, 2026-03, 2026-03
        Local LLM (Ollama)            :done, p3b, 2026-03, 2026-03
        Session memory                :done, p3c, 2026-03, 2026-03
        Data export (JSON/CSV)        :done, p3d, 2026-03, 2026-03
    section Phase 4 (Done)
        Multi-user auth               :done, p4a, 2026-03, 2026-03
        Scheduling + reminders        :done, p4b, 2026-03, 2026-03
        Longitudinal tracking         :done, p4c, 2026-03, 2026-03
        Deployment prep               :done, p4d, 2026-03, 2026-03
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
