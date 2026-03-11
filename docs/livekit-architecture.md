# LiveKit Receptionist — Architecture Guide

> **For AI tools:** This document is the authoritative reference for the LiveKit receptionist persona. When modifying any file under `talker/personas/` or `talker/livekit_agent.py`, read this document first. All diagrams use Mermaid syntax.

**Last updated:** 2026-03-11

---

## System Overview

How the receptionist fits into the LiveKit ecosystem — from the visitor's microphone to the agent's response.

```mermaid
graph LR
    subgraph "Visitor's Browser"
        MIC["🎤 Microphone"]
        SPK["🔊 Speaker"]
    end

    subgraph "LiveKit Cloud"
        ROOM["Room<br/>WebRTC audio routing"]
        STT["Deepgram Nova-3<br/>Speech → Text"]
        TTS["Cartesia Sonic-3<br/>Text → Speech"]
    end

    subgraph "Talker Agent Process"
        SESSION["AgentSession<br/>livekit_agent.py"]
        PERSONA["ReceptionistAgent<br/>personas/receptionist.py"]
        LLM["OpenAI GPT-4.1-mini<br/>Reasoning + tool selection"]
        TOOLS["Tool Registry<br/>7 @function_tool functions"]
    end

    MIC -->|WebRTC audio| ROOM
    ROOM -->|audio stream| STT
    STT -->|transcript| LLM
    LLM -->|tool calls| TOOLS
    TOOLS -->|results| LLM
    LLM -->|response text| TTS
    TTS -->|audio stream| ROOM
    ROOM -->|WebRTC audio| SPK

    SESSION --> PERSONA
    PERSONA --> LLM
    PERSONA --> TOOLS
```

---

## Voice Pipeline — What Happens Per Turn

Every time the visitor speaks, this sequence fires:

```mermaid
sequenceDiagram
    participant V as 🧑 Visitor
    participant VAD as Silero VAD
    participant STT as Deepgram STT
    participant TD as Turn Detector
    participant LLM as GPT-4.1-mini
    participant T as Tools
    participant TTS as Cartesia TTS

    V->>VAD: speaks into microphone
    VAD->>VAD: detect voice activity start/end
    VAD->>STT: audio segment
    STT->>TD: "I'm here to see Sarah Chen"
    TD->>TD: detect turn complete
    TD->>LLM: transcript + conversation history

    Note over LLM: Decides: need to look up Sarah Chen

    LLM->>T: lookup_tenant("Sarah Chen")
    T-->>LLM: {found: true, floor: 18, company: "Deloitte"}
    LLM->>T: check_availability("Sarah Chen")
    T-->>LLM: {available: true}

    Note over LLM: Composes natural response

    LLM-->>TTS: "Sarah Chen is on floor 18 with Deloitte. Take the lifts on the left."
    TTS-->>V: 🔊 audio response
```

---

## Agent Architecture — Class Hierarchy

```mermaid
classDiagram
    class Agent {
        <<LiveKit base>>
        +instructions: str
        +tools: list
    }

    class ReceptionistAgent {
        +instructions: RECEPTIONIST_INSTRUCTIONS
        +tools: 7 function_tools
    }

    class AgentSession {
        +stt: Deepgram
        +llm: OpenAI
        +tts: Cartesia
        +vad: Silero
        +turn_detection: Multilingual
        +start(room, agent)
        +generate_reply()
    }

    class AgentServer {
        +rtc_session(agent_name)
    }

    Agent <|-- ReceptionistAgent
    AgentServer --> AgentSession : creates
    AgentSession --> ReceptionistAgent : runs
```

---

## Tool Registry — What the Agent Can Do

Each tool is a standalone async function decorated with `@function_tool()`. The LLM decides when to call them based on conversation context.

```mermaid
graph TB
    subgraph "ReceptionistAgent Tools"
        direction TB
        LT["🔍 lookup_tenant<br/>Search building directory<br/>by name or company"]
        CA["📋 check_availability<br/>Is the person available<br/>to receive visitors?"]
        BI["🏢 get_building_info<br/>Facilities, transport,<br/>restaurants, amenities"]
        GW["🌤 get_weather<br/>Live London weather<br/>OpenWeatherMap API"]
        LV["📝 log_visitor<br/>Record arrival +<br/>link to visitor record"]
        RV["👤 recognize_visitor<br/>Find returning visitors<br/>by email or name"]
        REG["📋 register_visitor<br/>Silently register new<br/>visitors for tracking"]
    end

    subgraph "Data Sources"
        DIR["DIRECTORY dict<br/>12 entries: people + companies<br/>floor, suite, type"]
        AVAIL["_UNAVAILABLE dict<br/>Pre-set out-of-office<br/>+ 15% random chance"]
        BINFO["BUILDING_INFO dict<br/>15 topics: bathroom, parking,<br/>wifi, lifts, restaurants..."]
        API["OpenWeatherMap API<br/>GET /data/2.5/weather<br/>q=London,GB"]
        VDB["PostgreSQL<br/>visitors + visitor_logs<br/>via visitor_repo.py"]
    end

    LT --> DIR
    CA --> AVAIL
    BI --> BINFO
    GW --> API
    LV --> VDB
    RV --> VDB
    REG --> VDB
```

---

## Tool Decision Flow — How the LLM Picks Tools

This is the mental model the LLM follows (encoded in the system prompt):

```mermaid
flowchart TD
    START["Visitor says something"] --> INTENT{What do they need?}

    INTENT -->|"I'm here to see..."| LOOKUP["lookup_tenant(name)"]
    LOOKUP --> FOUND{Found?}
    FOUND -->|yes| AVAIL["check_availability(name)"]
    FOUND -->|no| CLARIFY["Ask to clarify name/company"]
    CLARIFY --> LOOKUP

    AVAIL --> AVAILABLE{Available?}
    AVAILABLE -->|yes| DIRECT["Give directions + log_visitor()"]
    AVAILABLE -->|no| WAIT["Explain reason, offer to wait<br/>mention coffee bar, seating"]

    INTENT -->|"Where is the..."| BUILDING["get_building_info(topic)"]
    BUILDING --> ANSWER_B["Answer with directions"]

    INTENT -->|"What's the weather..."| WEATHER["get_weather()"]
    WEATHER --> ANSWER_W["Comment naturally"]

    INTENT -->|small talk| CHAT["Respond naturally<br/>no tool needed"]

    INTENT -->|unclear| ASK["Ask a clarifying question<br/>one thing at a time"]
```

---

## Directory Data Model

```mermaid
erDiagram
    DIRECTORY {
        string key "lowercase lookup key"
        string contact "Person or desk name"
        int floor "Building floor number"
        string suite "Suite identifier"
        string company "Full company name"
        string type "law firm | consulting | hotel | restaurant | etc"
    }

    UNAVAILABLE {
        string key "lowercase person name"
        string reason "Human-readable reason"
    }

    BUILDING_INFO {
        string topic "bathroom | parking | wifi | lift | etc"
        string info "Natural language answer"
    }

    DIRECTORY ||--o| UNAVAILABLE : "may have"
```

### Current tenants (12 entries, 8 unique companies)

```mermaid
graph LR
    subgraph "Floor 8"
        F8["Meridian Health Group<br/>Dr. Tom Blake<br/>Suite 8A"]
    end
    subgraph "Floor 12"
        F12["Wardle Partners LLP<br/>James Wardle<br/>Suite 12A"]
    end
    subgraph "Floor 18"
        F18["Deloitte<br/>Sarah Chen<br/>Suite 18-20"]
    end
    subgraph "Floor 25"
        F25["Foresight Analytics<br/>Priya Kapoor<br/>Suite 25C"]
    end
    subgraph "Floors 31-35"
        F31["Aqua Shard — Floor 31"]
        F32["Oblix Restaurant — Floor 32"]
        F34["Shangri-La Hotel — Floors 34-52"]
    end
    subgraph "Floor 72"
        F72["The View from The Shard<br/>Observation Deck<br/>Floors 68-72"]
    end
```

---

## Fuzzy Matching — How Names Are Resolved

```mermaid
flowchart TD
    INPUT["User says a name"] --> LOWER["Lowercase + strip whitespace"]
    LOWER --> EXACT{Exact match<br/>in DIRECTORY keys?}
    EXACT -->|yes| RETURN["Return tenant data"]
    EXACT -->|no| SUB1{Query is substring<br/>of any key?}
    SUB1 -->|yes| RETURN
    SUB1 -->|no| SUB2{Any key is substring<br/>of query?}
    SUB2 -->|yes| RETURN
    SUB2 -->|no| COMPANY{Query matches<br/>company name field?}
    COMPANY -->|yes| RETURN
    COMPANY -->|no| NONE["Return None<br/>→ agent asks to clarify"]
```

---

## Conversation State Machine

Unlike the psychology assessor (which has formal states), the receptionist follows an implicit flow:

```mermaid
stateDiagram-v2
    [*] --> GREETING: visitor enters

    GREETING --> IDENTIFYING: "Who are you here to see?"
    IDENTIFYING --> LOOKING_UP: got a name
    IDENTIFYING --> IDENTIFYING: name unclear, ask again

    LOOKING_UP --> FOUND: tenant exists
    LOOKING_UP --> NOT_FOUND: no match
    NOT_FOUND --> IDENTIFYING: ask to clarify

    FOUND --> CHECKING: check availability
    CHECKING --> DIRECTING: person available
    CHECKING --> WAITING: person unavailable

    DIRECTING --> LOGGING: give floor + directions
    LOGGING --> DONE: log_visitor, wish them well

    WAITING --> DONE: offer coffee bar, seating

    GREETING --> HELPING: building question
    HELPING --> DONE: answer + offer more help
    HELPING --> GREETING: another question

    DONE --> [*]
```

---

## Capabilities — Pluggable Pipeline Modules

> **For AI tools:** Capabilities are NOT tools. They are pipeline plugins that process audio/text automatically on every turn and inject context for the LLM. Tools are called on demand by the LLM. Capabilities run whether the LLM asks for them or not.

```mermaid
graph TB
    subgraph "How Capabilities Differ From Tools"
        direction LR
        subgraph "Tools"
            T_WHEN["Called by LLM<br/>on demand"]
            T_WHAT["Return data to LLM<br/>as function result"]
            T_EX["e.g. lookup_tenant,<br/>get_weather"]
        end
        subgraph "Capabilities"
            C_WHEN["Run automatically<br/>every audio turn"]
            C_WHAT["Inject context into LLM<br/>before it responds"]
            C_EX["e.g. voice_analysis,<br/>sentiment detection"]
        end
    end
```

### Voice Analysis Capability — How It Works

```mermaid
sequenceDiagram
    participant MIC as 🎤 Visitor Audio
    participant LK as LiveKit Room
    participant CAP as VoiceAnalysis<br/>Capability
    participant PRAAT as Parselmouth<br/>(voice_features.py)
    participant MOOD as Mood Inference<br/>(rule engine)
    participant LLM as GPT-4.1-mini

    MIC->>LK: audio frames
    LK->>CAP: rtc.AudioStream events
    CAP->>CAP: buffer ~2 seconds

    Note over CAP: Every 2s chunk:

    CAP->>PRAAT: extract_features(audio)
    PRAAT-->>CAP: pitch, jitter, shimmer,<br/>HNR, speech_rate
    CAP->>MOOD: infer_mood(features)
    MOOD-->>CAP: moods + confidence

    CAP->>LLM: [Voice Analysis] Speaker mood: anxious<br/>Pitch: 240Hz, Rate: 4.1 w/s

    Note over LLM: Sees mood context BEFORE<br/>generating response.<br/>Adapts tone naturally.
```

### Mood Inference Rules

```mermaid
graph TB
    FEATURES["Acoustic Features"] --> RULES{Rule Engine}

    RULES -->|"pitch > 200 AND<br/>speech_rate > 3.5"| ANXIOUS["😰 anxious"]
    RULES -->|"jitter > 0.02 OR<br/>shimmer > 0.1"| STRESSED["😤 stressed"]
    RULES -->|"pitch < 120 AND<br/>speech_rate < 2.0"| LOW["😔 low_energy"]
    RULES -->|"pitch_std > 50 AND<br/>intensity > 75"| AGITATED["😠 agitated"]
    RULES -->|"speech_rate < 1.5 AND<br/>pitch_std > 30"| HESITANT["🤔 hesitant"]
    RULES -->|"pitch_std < 20 AND<br/>2.0 ≤ rate ≤ 3.5"| CALM["😌 calm"]
    RULES -->|"no strong signals"| NEUTRAL["😐 neutral"]

    ANXIOUS --> MULTI["Multiple moods<br/>can co-occur"]
    STRESSED --> MULTI
```

### Capability Architecture — Adding / Removing

```mermaid
classDiagram
    class BaseCapability {
        <<abstract>>
        +name: str
        +process_audio(audio, sample_rate, transcript) dict
        +get_context_prompt(results) str
        +get_tools() list
    }

    class VoiceAnalysisCapability {
        +name = "voice_analysis"
        +process_audio() → features + mood
        +get_context_prompt() → mood summary
        +get_tools() → [get_voice_analysis, get_voice_trend]
    }

    class FutureCapability {
        <<planned>>
        +name = "sentiment" | "emotion" | etc
    }

    BaseCapability <|-- VoiceAnalysisCapability
    BaseCapability <|-- FutureCapability
```

### Per-Persona Capability Configuration

```mermaid
graph LR
    subgraph "PERSONAS registry (livekit_agent.py)"
        R1["receptionist<br/>capabilities: [VoiceAnalysis]<br/>→ mood-aware responses"]
        R2["receptionist-basic<br/>capabilities: []<br/>→ no analysis"]
    end

    subgraph "How it wires up"
        BUILD["_build_agent()"]
        INJECT["Inject capability tools<br/>into agent._tools"]
        TAP["Tap audio stream<br/>via room.on('track_subscribed')"]
    end

    R1 --> BUILD
    BUILD --> INJECT
    BUILD --> TAP
```

Adding voice analysis to any persona = one line change:

```python
PERSONAS = {
    "my_persona": {
        "agent_class": MyAgent,
        "capabilities": [VoiceAnalysisCapability],  # ← add here
        # ...
    },
}
```

Removing = delete the entry from the list. No code changes in the persona itself.

### How the Receptionist Uses Voice Analysis

```mermaid
flowchart TD
    AUDIO["Visitor speaks"] --> CAP["VoiceAnalysis processes audio"]
    CAP --> CONTEXT["Context injected:<br/>'Speaker mood: anxious (elevated pitch)'"]

    CONTEXT --> LLM["LLM sees mood + transcript"]
    LLM --> DECIDE{How to adapt?}

    DECIDE -->|anxious/stressed| WARM["Extra warm, reassuring tone<br/>'Take your time, no rush'"]
    DECIDE -->|rushed/agitated| EFFICIENT["Quick, efficient response<br/>'Floor 18, lifts on the left'"]
    DECIDE -->|calm| NORMAL["Normal friendly tone<br/>small talk welcome"]
    DECIDE -->|distressed| CHECK["'Are you alright?<br/>Can I get you anything?'"]

    LLM -->|wants detail| TOOL1["get_voice_analysis()"]
    LLM -->|wants trend| TOOL2["get_voice_trend()"]
```

The LLM NEVER tells the visitor it's analyzing their voice. It just adapts — like a good receptionist who reads the room.

---

## File Map — Where Everything Lives

```mermaid
graph TB
    subgraph "talker/"
        LA["livekit_agent.py<br/>━━━━━━━━━━━━━━━<br/>• AgentServer + AgentSession<br/>• Persona registry + capabilities<br/>• Audio stream → capability pipeline<br/>• CLI: --persona arg<br/>• Entry point: __main__"]

        subgraph "personas/"
            PI["__init__.py"]
            REC["receptionist.py<br/>━━━━━━━━━━━━━━━<br/>• DIRECTORY (12 tenants)<br/>• BUILDING_INFO (15 topics)<br/>• _UNAVAILABLE (preset)<br/>• _fuzzy_find() helper<br/>• 7 @function_tool functions<br/>• Visitor tracking (silent)<br/>• RECEPTIONIST_INSTRUCTIONS<br/>• ReceptionistAgent(Agent)"]
        end

        subgraph "capabilities/"
            CAP_I["__init__.py"]
            CAP_B["base.py<br/>━━━━━━━━━━━━━━━<br/>• BaseCapability ABC<br/>• process_audio()<br/>• get_context_prompt()<br/>• get_tools()"]
            CAP_V["voice_analysis.py<br/>━━━━━━━━━━━━━━━<br/>• infer_mood() — 6 rules<br/>• VoiceAnalysisCapability<br/>• get_voice_analysis tool<br/>• get_voice_trend tool<br/>• _analysis_history deque"]
        end

        CONFIG["config.py<br/>━━━━━━━━━━━━━━━<br/>• livekit_url/key/secret<br/>• openweathermap_api_key"]

        VFEAT["services/voice_features.py<br/>━━━━━━━━━━━━━━━<br/>• extract_features()<br/>• Parselmouth: pitch, jitter,<br/>  shimmer, HNR, intensity"]
    end

    subgraph "tests/"
        TEST_R["test_receptionist.py<br/>29 tests"]
        TEST_C["test_capabilities.py<br/>21 tests"]
        TEST_A["test_assessor.py<br/>26 tests"]
        TEST_LK["test_livekit_routes.py<br/>6 tests"]
    end

    LA --> REC
    LA --> CAP_V
    CAP_V --> CAP_B
    CAP_V --> VFEAT
    REC --> CONFIG
    LA --> CONFIG
    TEST_R --> REC
    TEST_C --> CAP_V
    TEST_LK --> LA
```

---

## How to Add a New Tool

> **For AI tools:** Follow this pattern exactly when adding tools to any persona.

```mermaid
flowchart LR
    A["1. Write the function<br/>in personas/receptionist.py"] --> B["2. Add @function_tool()<br/>decorator"]
    B --> C["3. Add RunContext<br/>as first param"]
    C --> D["4. Write docstring<br/>LLM reads this!"]
    D --> E["5. Add to Agent's<br/>tools=[] list"]
    E --> F["6. Write test<br/>call via _func(None, ...)"]
```

**Template:**

```python
@function_tool()
async def my_new_tool(
    context: RunContext,
    param_name: str,
) -> dict[str, Any]:
    """One-line description the LLM will see.

    Args:
        param_name: What this parameter means.
    """
    # Business logic here — no framework coupling
    return {"key": "value"}
```

**Then add to the agent:**

```python
class ReceptionistAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=RECEPTIONIST_INSTRUCTIONS,
            tools=[
                lookup_tenant,
                check_availability,
                get_building_info,
                get_weather,
                log_visitor,
                recognize_visitor,
                register_visitor,
                my_new_tool,  # ← add here
            ],
        )
```

---

## How to Add a New Persona

> **For AI tools:** This is the pattern for creating new personas on the platform.

```mermaid
flowchart TD
    A["1. Create personas/new_persona.py"] --> B["2. Define tools as @function_tool()"]
    B --> C["3. Write INSTRUCTIONS string<br/>or load from Langfuse"]
    C --> D["4. Create NewPersonaAgent(Agent)<br/>with tools + instructions"]
    D --> E["5. Register in livekit_agent.py<br/>PERSONAS dict"]
    E --> F["6. Write tests/test_new_persona.py"]
    F --> G["7. Run: python -m talker.livekit_agent<br/>--persona new_persona"]
```

**In `livekit_agent.py`:**

```python
from talker.personas.new_persona import NewPersonaAgent

PERSONAS = {
    "receptionist": ReceptionistAgent,
    "new_persona": NewPersonaAgent,  # ← add here
}
```

---

## Running the Agent

```mermaid
flowchart LR
    subgraph "Development"
        DEV["python -m talker.livekit_agent dev<br/>--persona receptionist"]
        PLAY["LiveKit Playground<br/>agents-playground.livekit.io"]
        DEV <--> PLAY
    end

    subgraph "Console (no browser)"
        CON["python -m talker.livekit_agent console<br/>--persona receptionist"]
    end

    subgraph "Production"
        PROD["python -m talker.livekit_agent start<br/>--persona receptionist"]
        CLOUD["LiveKit Cloud<br/>Hosted rooms"]
        PROD <--> CLOUD
    end
```

**Required env vars:**

```mermaid
graph LR
    subgraph "Required"
        LK_URL["LIVEKIT_URL<br/>wss://your-project.livekit.cloud"]
        LK_KEY["LIVEKIT_API_KEY"]
        LK_SEC["LIVEKIT_API_SECRET"]
    end

    subgraph "Optional"
        OWM["OPENWEATHERMAP_API_KEY<br/>For live weather<br/>Falls back to mock if missing"]
    end
```

---

## Test Coverage Map

```mermaid
graph TB
    subgraph "test_receptionist.py — 29 tests"
        subgraph "Pure Functions (7)"
            T1["_fuzzy_find exact match"]
            T2["_fuzzy_find by person"]
            T3["_fuzzy_find case insensitive"]
            T4["_fuzzy_find substring"]
            T5["_fuzzy_find company name"]
            T6["_fuzzy_find not found"]
            T7["_fuzzy_find whitespace"]
        end

        subgraph "Tool Functions (15)"
            T8["lookup_tenant found"]
            T9["lookup_tenant not found"]
            T10["lookup_tenant fuzzy"]
            T11["check_availability unavailable"]
            T12["check_availability meeting"]
            T13["building_info bathroom"]
            T14["building_info parking"]
            T15["building_info restaurant"]
            T16["building_info unknown"]
            T17["weather fallback"]
            T18["visitor log"]
            T18b["visitor log untracked"]
            T18c["recognize visitor (no db)"]
            T18d["recognize visitor (no params)"]
            T18e["register visitor (no db)"]
        end

        subgraph "Agent + Data (7)"
            T19["instantiation"]
            T20["has instructions"]
            T21["has 7 tools"]
            T22["6+ unique tenants"]
            T23["all floors positive"]
            T24["essential topics"]
            T25["required fields"]
        end
    end

    subgraph "test_capabilities.py — 21 tests"
        subgraph "Mood Inference (10)"
            M1["neutral / no signals"]
            M2["anxious"]
            M3["stressed"]
            M4["low energy"]
            M5["agitated"]
            M6["hesitant"]
            M7["calm"]
            M8["empty features"]
            M9["confidence scaling"]
            M10["mood co-occurrence"]
        end

        subgraph "Capability Class (7)"
            C1["name property"]
            C2["is BaseCapability"]
            C3["process_audio output"]
            C4["updates history"]
            C5["context prompt format"]
            C6["exposes 2 tools"]
            C7["empty results → no context"]
        end

        subgraph "Voice Tools (4)"
            V1["analysis — no data"]
            V2["analysis — with data"]
            V3["trend — insufficient"]
            V4["trend — with history"]
        end
    end
```

---

## Edge Case Handling

How the agent handles situations that make conversations feel human:

```mermaid
graph TB
    subgraph "Person Not Found"
        NF1["Visitor: 'I'm here to see John Smith'"]
        NF2["lookup_tenant → not found"]
        NF3["Agent: 'I can't find a John Smith.<br/>Do you know which company they're with?'"]
        NF4["Visitor: 'Deloitte'"]
        NF5["lookup_tenant('Deloitte') → found, floor 18"]
        NF1 --> NF2 --> NF3 --> NF4 --> NF5
    end

    subgraph "Person Unavailable"
        UA1["lookup_tenant → found"]
        UA2["check_availability → unavailable:<br/>'in a meeting until 3pm'"]
        UA3["Agent: 'Priya's in a meeting until 3.<br/>There's a coffee bar on the ground floor<br/>if you'd like to wait.'"]
        UA1 --> UA2 --> UA3
    end

    subgraph "Building Question"
        BQ1["Visitor: 'Where's the loo?'"]
        BQ2["get_building_info('toilet') → match"]
        BQ3["Agent: 'Just past the lifts on<br/>the ground floor, to your left.'"]
        BQ1 --> BQ2 --> BQ3
    end

    subgraph "Weather / Small Talk"
        WT1["Visitor: 'Lovely day isn't it?'"]
        WT2["get_weather() → 14°C, partly cloudy"]
        WT3["Agent: 'Not bad for London! 14 degrees<br/>and partly cloudy. The view from<br/>the 72nd floor should be decent today.'"]
        WT1 --> WT2 --> WT3
    end
```
