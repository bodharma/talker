# The Shard Receptionist — LiveKit Voice Agent

> **Context:** This is the voice agent task from Dave's brief. It runs as a persona on the Talker platform using LiveKit as the voice transport.

## What it does

A voice-based AI receptionist for The Shard in London. A guest walks in, the agent greets them, figures out who they're visiting, looks them up in the building directory, and tells them which floor to go to — handling edge cases naturally along the way.

### Conversation flow

1. **Greeting** — warm, professional welcome to The Shard
2. **Visitor identification** — work out who they're here to see (name, company)
3. **Directory lookup** — tool call to find the tenant, return floor and suite
4. **Edge cases handled naturally:**
   - Person not found in directory → offer to check spelling, suggest similar names
   - Visitee not available / out of office → offer to leave a message or wait
   - Guest needs to wait → direct to the lobby seating area, offer refreshments
   - Building questions → bathrooms, parking, restaurants, observation deck
   - Real-world context → live weather via API, nearby transport info

### Tool calls

| Tool | What it does | Real or mock |
|---|---|---|
| `lookup_tenant` | Search building directory by name or company | Mock — returns tenant data from a dict |
| `check_availability` | Check if a specific person is available right now | Mock — random availability with reasons |
| `get_weather` | Current London weather | **Real** — OpenWeatherMap free API |
| `get_building_info` | Floor guide, facilities, restaurants, observation deck | Mock — static building knowledge |
| `log_visitor` | Record the visit + link to visitor record if tracked | **Real** — PostgreSQL when configured, console fallback |
| `recognize_visitor` | Find a returning visitor by email or name | **Real** — PostgreSQL visitor tracking |
| `register_visitor` | Silently register a new visitor for future recognition | **Real** — PostgreSQL visitor tracking |

### What makes it human

- Doesn't interrogate — asks naturally, one thing at a time
- Handles "I don't know the exact name" gracefully (fuzzy matching)
- Small talk capable — weather, the view from the 72nd floor, restaurant recommendations
- Knows when to stop asking and just help
- Varied responses — not robotic repetition
- Remembers returning visitors — silently recognizes by name/email, retrieves visit history for personalized conversation. Never says "let me register you" — just remembers, like a good receptionist

## How to run

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager
- LiveKit Cloud account (free tier — sign up with GitHub at [livekit.io](https://livekit.io))

### Setup

```bash
# Clone and install
git clone https://github.com/bodharma/talker.git
cd talker
uv sync

# Configure LiveKit credentials
cp .env.example .env
# Add your LIVEKIT_URL and LIVEKIT_API_KEY/SECRET from LiveKit Cloud dashboard
```

### Run locally

```bash
# Start the LiveKit agent
uv run python -m talker.livekit_agent --persona receptionist

# Connect via LiveKit Playground
# Go to https://agents-playground.livekit.io
# Enter your LiveKit Cloud URL and connect
```

### Run the receptionist directly (minimal setup)

The agent needs LiveKit credentials and optionally an OpenWeatherMap key for live weather. PostgreSQL is optional — without it, visitor tracking is disabled but everything else works.

```bash
# Minimal run
LIVEKIT_URL=wss://your-project.livekit.cloud \
LIVEKIT_API_KEY=your-key \
LIVEKIT_API_SECRET=your-secret \
uv run python -m talker.livekit_agent --persona receptionist
```

## Code structure

```
talker/
  livekit_agent.py          # LiveKit agent entrypoint — session setup, persona loading
  personas/
    receptionist.py         # Shard receptionist tools (7 @function_tool definitions)
    assessor.py             # Psychology assessor tools (existing Talker functionality)
  capabilities/
    base.py                 # BaseCapability ABC for pluggable pipeline modules
    voice_analysis.py       # Voice analysis + mood inference capability
  services/
    visitor_repo.py         # Visitor tracking repository (PostgreSQL)
    voice.py                # Voice provider abstraction (local / cloud / livekit)
  models/
    db.py                   # Visitor + VisitorLog ORM models
  routes/
    livekit.py              # LiveKit voice page + token endpoint (auth gating)
  templates/
    livekit_voice.html      # Embedded voice session UI
tests/
  test_receptionist.py      # 29 tests — tools, visitor tracking, data integrity
  test_assessor.py          # 26 tests — assessor persona tools
  test_capabilities.py      # 21 tests — voice analysis, mood inference
  test_livekit_routes.py    # 6 tests — token endpoint, voice page, auth gating
```

### Key design decisions

**Persona as configuration, not code** — the receptionist and assessor share the same agent engine. A persona defines: which tools are available, system prompt (via Langfuse), and conversation style. Adding a new persona = new tool file + Langfuse prompt.

**Tools are plain functions** — each `@function_tool()` is independently testable. No framework coupling in the business logic. The directory lookup doesn't know or care that it's being called by a voice agent.

**LiveKit as transport, not architecture** — LiveKit handles the room, audio routing, and STT/TTS pipeline. The agent logic (tools, prompts, conversation flow) is framework-agnostic and could run on the existing WebSocket pipeline or any other transport.

## Tests

```bash
# Run receptionist-specific tests
uv run pytest tests/test_receptionist.py -v

# Run all tests (including full Talker suite)
uv run pytest -v
```

Tests cover:
- Directory lookup — exact match, fuzzy match, company search, not found
- Availability checking — available, unavailable with reason, out of office
- Building info — known facilities, unknown queries
- Weather tool — API call with mock response
- Visitor logging — with and without DB tracking
- Visitor recognition — by email, by name, no DB fallback
- Visitor registration — with and without DB
- Agent instantiation, instruction content, tool count
- Data integrity — tenant count, floor validation, required fields

## Wider vision

This receptionist is one persona on a platform built for structured voice conversations. The same architecture powers a psychology pre-assessment agent that administers validated DSM-5 screening questionnaires (PHQ-9, GAD-7, PCL-5, ASRS), runs LLM-powered follow-up conversations, monitors for crisis language in real-time, and generates clinical reports.

The pattern is the same: greet a human, understand what they need, use tools to help them, handle edge cases naturally. Whether that's "which floor is Deloitte on?" or "over the last two weeks, how often have you felt down?" — it's the same agent doing different work.

See the [main README](../README.md) for the full platform overview and [`docs/architecture.md`](architecture.md) for the technical deep-dive.
