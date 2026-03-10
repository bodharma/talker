# Talker Phase 1 — MVP Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Working text-based psychology pre-assessment assistant with 4 screening instruments, conversational follow-up, and session history.

**Architecture:** PydanticAI agent framework with FastAPI + Jinja2 web UI. Orchestrator agent coordinates Screener and Conversation sub-agents. PostgreSQL for storage, OpenRouter for LLM, Langfuse for tracing.

**Tech Stack:** Python 3.10+, FastAPI, Jinja2, PydanticAI, SQLAlchemy async (asyncpg), Alembic, pydantic-settings, OpenRouter (via PydanticAI OpenRouterProvider), Langfuse, WeasyPrint (reports), PostgreSQL.

**Spec:** `docs/specs/2026-03-10-talker-design.md`

---

## Chunk 1: Project Foundation

### Task 1: Project Setup & Dependencies

**Files:**
- Modify: `pyproject.toml`
- Create: `.env.example`
- Create: `talker/config.py`
- Modify: `talker/main.py`

- [ ] **Step 1: Update pyproject.toml with all Phase 1 dependencies**

```toml
[project]
name = "talker"
version = "0.1.0"
description = "Psychology pre-assessment voice assistant"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "fastapi[standard]>=0.115.0",
    "jinja2>=3.1.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "pydantic-ai>=1.0.0",
    "langfuse>=2.0.0",
    "pyyaml>=6.0.0",
    "weasyprint>=62.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.27.0",
    "ruff>=0.8.0",
]
```

- [ ] **Step 2: Create .env.example**

```env
# Database
DATABASE_URL=postgresql+asyncpg://talker:talker@localhost:5432/talker

# OpenRouter
OPENROUTER_API_KEY=your-key-here
OPENROUTER_MODEL_CONVERSATION=anthropic/claude-sonnet-4-20250514
OPENROUTER_MODEL_SCREENER=anthropic/claude-haiku-4-20250414

# Langfuse
LANGFUSE_SECRET_KEY=your-secret-key
LANGFUSE_PUBLIC_KEY=your-public-key
LANGFUSE_HOST=https://cloud.langfuse.com

# App
APP_SECRET_KEY=change-me-in-production
ADMIN_TOKEN=change-me-in-production
DEBUG=true
```

- [ ] **Step 3: Create config.py with pydantic-settings**

```python
# talker/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://talker:talker@localhost:5432/talker"

    # OpenRouter
    openrouter_api_key: str = ""
    openrouter_model_conversation: str = "anthropic/claude-sonnet-4-20250514"
    openrouter_model_screener: str = "anthropic/claude-haiku-4-20250414"

    # Langfuse
    langfuse_secret_key: str = ""
    langfuse_public_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # App
    app_secret_key: str = "change-me-in-production"
    admin_token: str = "change-me-in-production"
    debug: bool = False
```

- [ ] **Step 4: Update main.py to minimal FastAPI app**

```python
# talker/main.py
from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from talker.config import Settings


@lru_cache
def get_settings() -> Settings:
    return Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Talker", lifespan=lifespan)

templates = Jinja2Templates(directory="talker/templates")
```

- [ ] **Step 5: Verify project installs and app starts**

Run: `uv sync && uv run python -c "from talker.main import app; print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .env.example talker/config.py talker/main.py
git commit -m "feat: project setup with FastAPI, pydantic-settings, and dependencies"
```

---

### Task 2: Database Models & Migrations

**Files:**
- Create: `talker/models/__init__.py`
- Create: `talker/models/db.py`
- Create: `talker/models/schemas.py`
- Create: `talker/services/__init__.py`
- Create: `talker/services/database.py`
- Create: `alembic.ini`
- Create: `migrations/env.py`
- Create: `migrations/script.py.mako`
- Create: `migrations/versions/` (empty dir)
- Test: `tests/test_models.py`

- [ ] **Step 1: Write tests for Pydantic schemas**

```python
# tests/test_models.py
import pytest
from talker.models.schemas import (
    SessionCreate,
    SessionState,
    ScreeningResult,
    InstrumentMetadata,
)


def test_session_create_defaults():
    session = SessionCreate()
    assert session.mode == "web"
    assert session.memory_consent is False
    assert session.voice_consent is False


def test_session_state_enum():
    assert SessionState.CREATED == "created"
    assert SessionState.INTAKE == "intake"
    assert SessionState.SCREENING == "screening"
    assert SessionState.FOLLOW_UP == "follow_up"
    assert SessionState.SUMMARY == "summary"
    assert SessionState.COMPLETED == "completed"
    assert SessionState.ABANDONED == "abandoned"
    assert SessionState.INTERRUPTED_BY_SAFETY == "interrupted_by_safety"


def test_screening_result_validation():
    result = ScreeningResult(
        instrument_id="phq-9",
        score=14,
        severity="moderate",
        raw_answers={"q1": 2, "q2": 3},
        flagged_items=[9],
    )
    assert result.score == 14
    assert result.flagged_items == [9]


def test_instrument_metadata():
    meta = InstrumentMetadata(
        id="phq-9",
        name="Patient Health Questionnaire-9",
        description="Depression screening",
        item_count=9,
    )
    assert meta.id == "phq-9"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL — modules not found

- [ ] **Step 3: Create Pydantic schemas**

```python
# talker/models/__init__.py
```

```python
# talker/models/schemas.py
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class SessionState(StrEnum):
    CREATED = "created"
    INTAKE = "intake"
    SCREENING = "screening"
    FOLLOW_UP = "follow_up"
    SUMMARY = "summary"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    INTERRUPTED_BY_SAFETY = "interrupted_by_safety"


class SessionCreate(BaseModel):
    mode: str = "web"
    memory_consent: bool = False
    voice_consent: bool = False


class SessionResponse(BaseModel):
    id: int
    state: SessionState
    mode: str
    memory_consent: bool
    voice_consent: bool
    created_at: datetime
    completed_at: datetime | None = None


class ScreeningResult(BaseModel):
    instrument_id: str
    score: int
    severity: str
    raw_answers: dict = Field(default_factory=dict)
    flagged_items: list[int] = Field(default_factory=list)


class ConversationObservation(BaseModel):
    topic: str
    observation: str
    severity_hint: str | None = None


class SessionSummary(BaseModel):
    session_id: int
    instruments_completed: list[str]
    recommendations: list[str]
    areas_to_explore: list[str]
    observations: list[ConversationObservation] = Field(default_factory=list)


class InstrumentMetadata(BaseModel):
    id: str
    name: str
    description: str
    item_count: int


class SafetyEvent(BaseModel):
    session_id: int
    trigger: str
    agent: str
    message_shown: str
    resources_provided: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Create SQLAlchemy models**

```python
# talker/models/db.py
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Boolean, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(AsyncAttrs, DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), default="default")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    sessions: Mapped[list["Session"]] = relationship(back_populates="user")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    state: Mapped[str] = mapped_column(String(50), default="created")
    mode: Mapped[str] = mapped_column(String(20), default="web")
    memory_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    voice_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="sessions")
    screenings: Mapped[list["SessionScreening"]] = relationship(back_populates="session")
    conversations: Mapped[list["SessionConversation"]] = relationship(back_populates="session")
    summary: Mapped["SessionSummaryRecord | None"] = relationship(back_populates="session")
    safety_events: Mapped[list["SafetyEventRecord"]] = relationship(back_populates="session")


class SessionScreening(Base):
    __tablename__ = "session_screenings"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    instrument_id: Mapped[str] = mapped_column(String(50))
    score: Mapped[int] = mapped_column(Integer)
    severity: Mapped[str] = mapped_column(String(50))
    raw_answers: Mapped[dict] = mapped_column(JSONB, default=dict)
    flagged_items: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    session: Mapped["Session"] = relationship(back_populates="screenings")


class SessionConversation(Base):
    __tablename__ = "session_conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    transcript: Mapped[str] = mapped_column(Text, default="")
    observations: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    session: Mapped["Session"] = relationship(back_populates="conversations")


class SessionSummaryRecord(Base):
    __tablename__ = "session_summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), unique=True)
    instruments_completed: Mapped[list] = mapped_column(JSONB, default=list)
    recommendations: Mapped[list] = mapped_column(JSONB, default=list)
    areas_to_explore: Mapped[list] = mapped_column(JSONB, default=list)
    observations: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    session: Mapped["Session"] = relationship(back_populates="summary")


class SafetyEventRecord(Base):
    __tablename__ = "safety_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    trigger: Mapped[str] = mapped_column(String(255))
    agent: Mapped[str] = mapped_column(String(50))
    message_shown: Mapped[str] = mapped_column(Text)
    resources_provided: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    session: Mapped["Session"] = relationship(back_populates="safety_events")
```

- [ ] **Step 6: Create database service**

```python
# talker/services/__init__.py
```

```python
# talker/services/database.py
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from talker.config import Settings


def create_engine(settings: Settings):
    return create_async_engine(settings.database_url, echo=settings.debug)


def create_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    engine = create_engine(settings)
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_db(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        yield session
```

- [ ] **Step 7: Set up Alembic**

Run: `uv run alembic init migrations`

Then edit `alembic.ini` to set `sqlalchemy.url` placeholder, and edit `migrations/env.py` to:
- Import `talker.models.db.Base`
- Read `DATABASE_URL` from environment
- Set `target_metadata = Base.metadata`
- Configure async engine support

- [ ] **Step 8: Generate initial migration**

Run: `uv run alembic revision --autogenerate -m "initial schema"`
Expected: Migration file created in `migrations/versions/`

- [ ] **Step 9: Commit**

```bash
git add talker/models/ talker/services/ alembic.ini migrations/ tests/test_models.py
git commit -m "feat: database models, schemas, and Alembic migrations"
```

---

### Task 3: Screening Instrument Definitions

**Files:**
- Create: `talker/instruments/phq-9.yaml`
- Create: `talker/instruments/gad-7.yaml`
- Create: `talker/instruments/pcl-5.yaml`
- Create: `talker/instruments/asrs.yaml`
- Create: `talker/services/instruments.py`
- Test: `tests/test_instruments.py`

- [ ] **Step 1: Write tests for instrument loading and scoring**

```python
# tests/test_instruments.py
import pytest
from talker.services.instruments import InstrumentLoader, InstrumentDefinition


def test_load_phq9():
    loader = InstrumentLoader("talker/instruments")
    instrument = loader.load("phq-9")
    assert instrument.metadata.id == "phq-9"
    assert instrument.metadata.name == "Patient Health Questionnaire-9"
    assert len(instrument.questions) == 9
    assert len(instrument.response_options) > 0


def test_load_all_instruments():
    loader = InstrumentLoader("talker/instruments")
    instruments = loader.load_all()
    assert len(instruments) >= 4
    ids = [i.metadata.id for i in instruments]
    assert "phq-9" in ids
    assert "gad-7" in ids


def test_score_phq9_minimal():
    loader = InstrumentLoader("talker/instruments")
    instrument = loader.load("phq-9")
    # All zeros = minimal
    answers = {f"q{i}": 0 for i in range(1, 10)}
    result = instrument.score(answers)
    assert result.score == 0
    assert result.severity == "minimal"


def test_score_phq9_moderate():
    loader = InstrumentLoader("talker/instruments")
    instrument = loader.load("phq-9")
    # Score of 14 = moderate
    answers = {f"q{i}": 2 for i in range(1, 8)}  # 7 * 2 = 14
    answers["q8"] = 0
    answers["q9"] = 0
    result = instrument.score(answers)
    assert result.score == 14
    assert result.severity == "moderate"


def test_score_phq9_flags_item9():
    loader = InstrumentLoader("talker/instruments")
    instrument = loader.load("phq-9")
    answers = {f"q{i}": 0 for i in range(1, 10)}
    answers["q9"] = 1  # suicidal ideation item, any non-zero flags
    result = instrument.score(answers)
    assert 9 in result.flagged_items
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_instruments.py -v`
Expected: FAIL

- [ ] **Step 3: Create PHQ-9 instrument definition**

```yaml
# talker/instruments/phq-9.yaml
metadata:
  id: phq-9
  name: "Patient Health Questionnaire-9"
  description: "Screens for depression severity"
  citation: "Kroenke K, Spitzer RL, Williams JB. J Gen Intern Med. 2001;16(9):606-613."
  item_count: 9

response_options:
  - label: "Not at all"
    value: 0
  - label: "Several days"
    value: 1
  - label: "More than half the days"
    value: 2
  - label: "Nearly every day"
    value: 3

questions:
  - id: q1
    text: "Little interest or pleasure in doing things"
  - id: q2
    text: "Feeling down, depressed, or hopeless"
  - id: q3
    text: "Trouble falling or staying asleep, or sleeping too much"
  - id: q4
    text: "Feeling tired or having little energy"
  - id: q5
    text: "Poor appetite or overeating"
  - id: q6
    text: "Feeling bad about yourself — or that you are a failure or have let yourself or your family down"
  - id: q7
    text: "Trouble concentrating on things, such as reading the newspaper or watching television"
  - id: q8
    text: "Moving or speaking so slowly that other people could have noticed? Or the opposite — being so fidgety or restless that you have been moving around a lot more than usual"
  - id: q9
    text: "Thoughts that you would be better off dead or of hurting yourself in some way"

scoring:
  method: sum
  thresholds:
    - max: 4
      severity: "minimal"
    - max: 9
      severity: "mild"
    - max: 14
      severity: "moderate"
    - max: 19
      severity: "moderately severe"
    - max: 27
      severity: "severe"

flags:
  - item: q9
    condition: "greater_than"
    value: 0
    flag_as: 9
    reason: "Suicidal ideation indicator"

follow_up_hints:
  - "Explore duration and onset of depressive symptoms"
  - "Ask about impact on daily functioning, work, and relationships"
  - "If item 9 flagged, gently explore suicidal thoughts with safety protocol"
```

- [ ] **Step 4: Create GAD-7 instrument definition**

```yaml
# talker/instruments/gad-7.yaml
metadata:
  id: gad-7
  name: "Generalized Anxiety Disorder 7-item"
  description: "Screens for generalized anxiety disorder severity"
  citation: "Spitzer RL, Kroenke K, Williams JBW, Löwe B. Arch Intern Med. 2006;166(10):1092-1097."
  item_count: 7

response_options:
  - label: "Not at all"
    value: 0
  - label: "Several days"
    value: 1
  - label: "More than half the days"
    value: 2
  - label: "Nearly every day"
    value: 3

questions:
  - id: q1
    text: "Feeling nervous, anxious, or on edge"
  - id: q2
    text: "Not being able to stop or control worrying"
  - id: q3
    text: "Worrying too much about different things"
  - id: q4
    text: "Trouble relaxing"
  - id: q5
    text: "Being so restless that it's hard to sit still"
  - id: q6
    text: "Becoming easily annoyed or irritable"
  - id: q7
    text: "Feeling afraid as if something awful might happen"

scoring:
  method: sum
  thresholds:
    - max: 4
      severity: "minimal"
    - max: 9
      severity: "mild"
    - max: 14
      severity: "moderate"
    - max: 21
      severity: "severe"

flags: []

follow_up_hints:
  - "Explore specific worry triggers and patterns"
  - "Ask about physical symptoms of anxiety (heart racing, sweating, tension)"
  - "Assess impact on sleep, work, and social activities"
```

- [ ] **Step 5: Create PCL-5 instrument definition**

```yaml
# talker/instruments/pcl-5.yaml
metadata:
  id: pcl-5
  name: "PTSD Checklist for DSM-5"
  description: "Screens for PTSD symptom severity"
  citation: "Weathers FW, et al. National Center for PTSD. 2013."
  item_count: 20

response_options:
  - label: "Not at all"
    value: 0
  - label: "A little bit"
    value: 1
  - label: "Moderately"
    value: 2
  - label: "Quite a bit"
    value: 3
  - label: "Extremely"
    value: 4

questions:
  - id: q1
    text: "Repeated, disturbing, and unwanted memories of the stressful experience"
  - id: q2
    text: "Repeated, disturbing dreams of the stressful experience"
  - id: q3
    text: "Suddenly feeling or acting as if the stressful experience were actually happening again (as if you were actually back there reliving it)"
  - id: q4
    text: "Feeling very upset when something reminded you of the stressful experience"
  - id: q5
    text: "Having strong physical reactions when something reminded you of the stressful experience (for example, heart pounding, trouble breathing, sweating)"
  - id: q6
    text: "Avoiding memories, thoughts, or feelings related to the stressful experience"
  - id: q7
    text: "Avoiding external reminders of the stressful experience (for example, people, places, conversations, activities, objects, or situations)"
  - id: q8
    text: "Trouble remembering important parts of the stressful experience"
  - id: q9
    text: "Having strong negative beliefs about yourself, other people, or the world (for example, having thoughts such as: I am bad, there is something seriously wrong with me, no one can be trusted, the world is completely dangerous)"
  - id: q10
    text: "Blaming yourself or someone else for the stressful experience or what happened after it"
  - id: q11
    text: "Having strong negative feelings such as fear, horror, anger, guilt, or shame"
  - id: q12
    text: "Loss of interest in activities that you used to enjoy"
  - id: q13
    text: "Feeling distant or cut off from other people"
  - id: q14
    text: "Trouble experiencing positive feelings (for example, being unable to feel happiness or have loving feelings for people close to you)"
  - id: q15
    text: "Irritable behavior, angry outbursts, or acting aggressively"
  - id: q16
    text: "Taking too many risks or doing things that could cause you harm"
  - id: q17
    text: "Being 'superalert' or watchful or on guard"
  - id: q18
    text: "Feeling jumpy or easily startled"
  - id: q19
    text: "Having difficulty concentrating"
  - id: q20
    text: "Trouble falling or staying asleep"

scoring:
  method: sum
  thresholds:
    - max: 32
      severity: "below threshold"
    - max: 80
      severity: "above threshold"

flags:
  - item: q16
    condition: "greater_than"
    value: 2
    flag_as: 16
    reason: "Risk-taking behavior at high level"

follow_up_hints:
  - "Ask about the nature of the traumatic experience (without forcing detail)"
  - "Explore avoidance patterns and their impact on daily life"
  - "Assess hyperarousal symptoms and sleep disruption"
```

- [ ] **Step 6: Create ASRS instrument definition**

```yaml
# talker/instruments/asrs.yaml
metadata:
  id: asrs
  name: "Adult ADHD Self-Report Scale v1.1 Screener"
  description: "Screens for ADHD in adults (6-item screener)"
  citation: "Kessler RC, et al. Psychol Med. 2005;35(2):245-256."
  item_count: 6

response_options:
  - label: "Never"
    value: 0
  - label: "Rarely"
    value: 1
  - label: "Sometimes"
    value: 2
  - label: "Often"
    value: 3
  - label: "Very often"
    value: 4

questions:
  - id: q1
    text: "How often do you have trouble wrapping up the final details of a project, once the challenging parts have been done?"
    scoring_threshold: 2
  - id: q2
    text: "How often do you have difficulty getting things in order when you have to do a task that requires organization?"
    scoring_threshold: 2
  - id: q3
    text: "How often do you have problems remembering appointments or obligations?"
    scoring_threshold: 2
  - id: q4
    text: "When you have a task that requires a lot of thought, how often do you avoid or delay getting started?"
    scoring_threshold: 2
  - id: q5
    text: "How often do you fidget or squirm with your hands or feet when you have to sit down for a long time?"
    scoring_threshold: 3
  - id: q6
    text: "How often do you feel overly active and compelled to do things, like you were driven by a motor?"
    scoring_threshold: 3

scoring:
  method: asrs_screener
  description: "Each item has its own threshold. Items 1-4 score if >= 2 (Sometimes). Items 5-6 score if >= 3 (Often). Total flagged items >= 4 suggests ADHD."
  thresholds:
    - max: 3
      severity: "below threshold"
    - max: 6
      severity: "above threshold"

flags: []

follow_up_hints:
  - "Explore whether symptoms have been present since childhood"
  - "Ask about impact on work, relationships, and daily organization"
  - "Assess whether symptoms cause significant impairment"
```

- [ ] **Step 7: Create instrument loader and scoring service**

```python
# talker/services/instruments.py
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from talker.models.schemas import InstrumentMetadata, ScreeningResult


class InstrumentQuestion(BaseModel):
    id: str
    text: str
    scoring_threshold: int | None = None


class ResponseOption(BaseModel):
    label: str
    value: int


class ScoringThreshold(BaseModel):
    max: int
    severity: str


class FlagRule(BaseModel):
    item: str
    condition: str
    value: int
    flag_as: int
    reason: str


class ScoringConfig(BaseModel):
    method: str
    description: str | None = None
    thresholds: list[ScoringThreshold]


class InstrumentDefinition(BaseModel):
    metadata: InstrumentMetadata
    response_options: list[ResponseOption]
    questions: list[InstrumentQuestion]
    scoring: ScoringConfig
    flags: list[FlagRule] = Field(default_factory=list)
    follow_up_hints: list[str] = Field(default_factory=list)

    def score(self, answers: dict[str, int]) -> ScreeningResult:
        if self.scoring.method == "sum":
            total = sum(answers.get(q.id, 0) for q in self.questions)
        elif self.scoring.method == "asrs_screener":
            total = 0
            for q in self.questions:
                threshold = q.scoring_threshold or 2
                if answers.get(q.id, 0) >= threshold:
                    total += 1
        else:
            total = sum(answers.get(q.id, 0) for q in self.questions)

        severity = self.scoring.thresholds[-1].severity
        for t in self.scoring.thresholds:
            if total <= t.max:
                severity = t.severity
                break

        flagged = []
        for rule in self.flags:
            answer_val = answers.get(rule.item, 0)
            if rule.condition == "greater_than" and answer_val > rule.value:
                flagged.append(rule.flag_as)

        return ScreeningResult(
            instrument_id=self.metadata.id,
            score=total,
            severity=severity,
            raw_answers=answers,
            flagged_items=flagged,
        )


class InstrumentLoader:
    def __init__(self, instruments_dir: str):
        self.instruments_dir = Path(instruments_dir)

    def load(self, instrument_id: str) -> InstrumentDefinition:
        path = self.instruments_dir / f"{instrument_id}.yaml"
        with open(path) as f:
            data = yaml.safe_load(f)
        return InstrumentDefinition(**data)

    def load_all(self) -> list[InstrumentDefinition]:
        instruments = []
        for path in sorted(self.instruments_dir.glob("*.yaml")):
            with open(path) as f:
                data = yaml.safe_load(f)
            instruments.append(InstrumentDefinition(**data))
        return instruments
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/test_instruments.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 9: Commit**

```bash
git add talker/instruments/ talker/services/instruments.py tests/test_instruments.py
git commit -m "feat: screening instrument definitions and scoring engine"
```

---

## Chunk 2: Agent Layer

### Task 4: LLM & Tracing Services

**Files:**
- Create: `talker/services/llm.py`
- Create: `talker/services/tracing.py`
- Test: `tests/test_llm.py`

- [ ] **Step 1: Write test for LLM service creation**

```python
# tests/test_llm.py
from unittest.mock import patch

from talker.services.llm import create_agent_model
from talker.config import Settings


def test_create_agent_model_returns_model():
    settings = Settings(openrouter_api_key="test-key")
    model = create_agent_model(settings, role="conversation")
    assert model is not None


def test_create_agent_model_screener():
    settings = Settings(openrouter_api_key="test-key")
    model = create_agent_model(settings, role="screener")
    assert model is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_llm.py -v`
Expected: FAIL

- [ ] **Step 3: Implement LLM service**

```python
# talker/services/llm.py
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from talker.config import Settings


def create_agent_model(settings: Settings, role: str = "conversation") -> OpenAIChatModel:
    """Create a PydanticAI-compatible model via OpenRouter."""
    model_name = (
        settings.openrouter_model_conversation
        if role == "conversation"
        else settings.openrouter_model_screener
    )
    provider = OpenRouterProvider(api_key=settings.openrouter_api_key)
    return OpenAIChatModel(model_name, provider=provider)
```

- [ ] **Step 4: Implement Langfuse tracing service**

```python
# talker/services/tracing.py
from langfuse import Langfuse

from talker.config import Settings


_langfuse: Langfuse | None = None


def init_langfuse(settings: Settings) -> Langfuse | None:
    """Initialize Langfuse client. Returns None if not configured."""
    global _langfuse
    if not settings.langfuse_secret_key:
        return None
    _langfuse = Langfuse(
        secret_key=settings.langfuse_secret_key,
        public_key=settings.langfuse_public_key,
        host=settings.langfuse_host,
    )
    return _langfuse


def get_langfuse() -> Langfuse | None:
    return _langfuse


def create_trace(session_id: int, agent_name: str):
    """Create a Langfuse trace for an agent interaction."""
    lf = get_langfuse()
    if lf is None:
        return None
    return lf.trace(
        name=f"talker-{agent_name}",
        session_id=str(session_id),
        metadata={"agent": agent_name},
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_llm.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add talker/services/llm.py talker/services/tracing.py tests/test_llm.py
git commit -m "feat: LLM service (OpenRouter) and Langfuse tracing"
```

---

### Task 5: Safety Monitor

**Files:**
- Create: `talker/agents/__init__.py`
- Create: `talker/agents/safety.py`
- Test: `tests/test_safety.py`

- [ ] **Step 1: Write tests for safety monitor**

```python
# tests/test_safety.py
import pytest
from talker.agents.safety import SafetyMonitor, SafetyInterrupt


def test_safe_message():
    monitor = SafetyMonitor()
    result = monitor.check("I've been feeling tired lately")
    assert result is None


def test_detects_suicidal_ideation():
    monitor = SafetyMonitor()
    result = monitor.check("I want to kill myself")
    assert result is not None
    assert isinstance(result, SafetyInterrupt)
    assert len(result.resources) > 0


def test_detects_self_harm():
    monitor = SafetyMonitor()
    result = monitor.check("I've been cutting myself")
    assert result is not None


def test_detects_harm_to_others():
    monitor = SafetyMonitor()
    result = monitor.check("I want to hurt someone")
    assert result is not None


def test_case_insensitive():
    monitor = SafetyMonitor()
    result = monitor.check("I WANT TO KILL MYSELF")
    assert result is not None


def test_crisis_resources_included():
    monitor = SafetyMonitor()
    result = monitor.check("I want to end my life")
    assert "988" in str(result.resources) or "Suicide" in str(result.resources)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_safety.py -v`
Expected: FAIL

- [ ] **Step 3: Implement Safety Monitor**

```python
# talker/agents/__init__.py
```

```python
# talker/agents/safety.py
import re
from dataclasses import dataclass, field


CRISIS_RESOURCES = [
    "988 Suicide & Crisis Lifeline: Call or text 988 (US)",
    "Crisis Text Line: Text HOME to 741741",
    "International Association for Suicide Prevention: https://www.iasp.info/resources/Crisis_Centres/",
    "Emergency Services: Call 911 (US) or your local emergency number",
]

# Patterns that indicate immediate safety concerns
CRISIS_PATTERNS = [
    r"\b(kill|end)\s+(my\s*self|my\s*life|it\s*all)\b",
    r"\bsuicid(e|al)\b",
    r"\bwant\s+to\s+die\b",
    r"\bbetter\s+off\s+dead\b",
    r"\bno\s+reason\s+to\s+live\b",
    r"\b(cutting|hurting|harming)\s+(my\s*self|myself)\b",
    r"\bself[- ]?harm\b",
    r"\bwant\s+to\s+hurt\s+(someone|somebody|people|others)\b",
    r"\bgoing\s+to\s+hurt\b",
    r"\bplan\s+to\s+(kill|die|end)\b",
]


@dataclass
class SafetyInterrupt:
    trigger: str
    message: str
    resources: list[str] = field(default_factory=lambda: list(CRISIS_RESOURCES))


class SafetyMonitor:
    def __init__(self):
        self._patterns = [re.compile(p, re.IGNORECASE) for p in CRISIS_PATTERNS]

    def check(self, text: str) -> SafetyInterrupt | None:
        """Check text for crisis indicators. Returns SafetyInterrupt if detected."""
        for pattern in self._patterns:
            match = pattern.search(text)
            if match:
                return SafetyInterrupt(
                    trigger=match.group(),
                    message=(
                        "I'm concerned about what you've shared. Your safety is the most important thing right now. "
                        "Please reach out to one of these resources — they are available 24/7 and can help:"
                    ),
                )
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_safety.py -v`
Expected: PASS (all 6 tests)

- [ ] **Step 5: Commit**

```bash
git add talker/agents/ tests/test_safety.py
git commit -m "feat: safety monitor with crisis detection and resources"
```

---

### Task 6: Screener Agent

**Files:**
- Create: `talker/agents/screener.py`
- Test: `tests/test_screener.py`

- [ ] **Step 1: Write tests for screener agent**

```python
# tests/test_screener.py
import pytest
from talker.agents.screener import ScreenerAgent
from talker.services.instruments import InstrumentLoader


@pytest.fixture
def loader():
    return InstrumentLoader("talker/instruments")


def test_screener_loads_instrument(loader):
    agent = ScreenerAgent(loader)
    agent.start_instrument("phq-9")
    assert agent.current_instrument is not None
    assert agent.current_question_index == 0


def test_screener_gets_first_question(loader):
    agent = ScreenerAgent(loader)
    agent.start_instrument("phq-9")
    q = agent.get_current_question()
    assert q is not None
    assert "interest or pleasure" in q.text.lower()


def test_screener_records_answer_and_advances(loader):
    agent = ScreenerAgent(loader)
    agent.start_instrument("phq-9")
    agent.record_answer(0)
    assert agent.current_question_index == 1


def test_screener_completes_instrument(loader):
    agent = ScreenerAgent(loader)
    agent.start_instrument("phq-9")
    for i in range(9):
        agent.record_answer(1)
    result = agent.get_result()
    assert result is not None
    assert result.instrument_id == "phq-9"
    assert result.score == 9
    assert result.severity == "mild"


def test_screener_is_complete(loader):
    agent = ScreenerAgent(loader)
    agent.start_instrument("gad-7")
    for i in range(7):
        agent.record_answer(0)
    assert agent.is_complete()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_screener.py -v`
Expected: FAIL

- [ ] **Step 3: Implement Screener Agent**

```python
# talker/agents/screener.py
from talker.models.schemas import ScreeningResult
from talker.services.instruments import InstrumentDefinition, InstrumentLoader, InstrumentQuestion


class ScreenerAgent:
    """Runs validated screening instruments. Asks questions exactly as defined."""

    def __init__(self, loader: InstrumentLoader):
        self.loader = loader
        self.current_instrument: InstrumentDefinition | None = None
        self.current_question_index: int = 0
        self.answers: dict[str, int] = {}

    def start_instrument(self, instrument_id: str) -> None:
        self.current_instrument = self.loader.load(instrument_id)
        self.current_question_index = 0
        self.answers = {}

    def get_current_question(self) -> InstrumentQuestion | None:
        if self.current_instrument is None or self.is_complete():
            return None
        return self.current_instrument.questions[self.current_question_index]

    def record_answer(self, value: int) -> None:
        if self.current_instrument is None:
            return
        q = self.current_instrument.questions[self.current_question_index]
        self.answers[q.id] = value
        self.current_question_index += 1

    def is_complete(self) -> bool:
        if self.current_instrument is None:
            return False
        return self.current_question_index >= len(self.current_instrument.questions)

    def get_result(self) -> ScreeningResult | None:
        if self.current_instrument is None or not self.is_complete():
            return None
        return self.current_instrument.score(self.answers)

    def get_progress(self) -> tuple[int, int]:
        if self.current_instrument is None:
            return 0, 0
        return self.current_question_index, len(self.current_instrument.questions)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_screener.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Commit**

```bash
git add talker/agents/screener.py tests/test_screener.py
git commit -m "feat: screener agent for validated instrument administration"
```

---

### Task 7: Conversation Agent

**Files:**
- Create: `talker/agents/conversation.py`
- Test: `tests/test_conversation.py`

- [ ] **Step 1: Write tests for conversation agent**

```python
# tests/test_conversation.py
import pytest
from talker.agents.conversation import ConversationAgent, ConversationContext
from talker.models.schemas import ScreeningResult


def test_conversation_context_creation():
    results = [
        ScreeningResult(
            instrument_id="phq-9",
            score=14,
            severity="moderate",
            raw_answers={},
            flagged_items=[9],
        )
    ]
    ctx = ConversationContext(screening_results=results)
    assert len(ctx.screening_results) == 1
    assert ctx.screening_results[0].severity == "moderate"


def test_conversation_agent_creates():
    agent = ConversationAgent()
    assert agent is not None


def test_build_system_prompt():
    results = [
        ScreeningResult(
            instrument_id="phq-9",
            score=14,
            severity="moderate",
            raw_answers={},
            flagged_items=[9],
        )
    ]
    ctx = ConversationContext(screening_results=results)
    agent = ConversationAgent()
    prompt = agent.build_system_prompt(ctx)
    assert "phq-9" in prompt.lower()
    assert "moderate" in prompt.lower()
    assert "not a medical" in prompt.lower() or "not a diagnosis" in prompt.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_conversation.py -v`
Expected: FAIL

- [ ] **Step 3: Implement Conversation Agent**

```python
# talker/agents/conversation.py
from pydantic import BaseModel, Field

from talker.models.schemas import ConversationObservation, ScreeningResult


class ConversationContext(BaseModel):
    screening_results: list[ScreeningResult] = Field(default_factory=list)
    prior_observations: list[ConversationObservation] = Field(default_factory=list)


class ConversationAgent:
    """Conducts open-ended follow-up conversations based on screening results.

    Uses an LLM to explore flagged areas. The actual LLM call is handled
    externally (by the orchestrator) — this agent builds prompts and
    parses responses.
    """

    SYSTEM_PROMPT_TEMPLATE = """You are a compassionate mental health pre-assessment assistant conducting a follow-up conversation.

IMPORTANT DISCLAIMERS:
- You are NOT a medical professional and this is NOT a diagnosis
- You are helping the user understand their symptoms to prepare for a professional consultation
- Never diagnose or prescribe treatment
- If you detect any crisis indicators, immediately provide crisis resources

SCREENING RESULTS:
{screening_summary}

YOUR ROLE:
- Explore the flagged areas conversationally: duration, triggers, daily life impact, history
- Be warm, non-judgmental, and patient
- Ask one question at a time
- Validate the user's experiences
- Focus on understanding, not fixing

Respond conversationally. Keep responses concise (2-3 sentences max) and end with a single follow-up question."""

    def build_system_prompt(self, context: ConversationContext) -> str:
        summaries = []
        for result in context.screening_results:
            summary = f"- {result.instrument_id}: score {result.score}, severity: {result.severity}"
            if result.flagged_items:
                summary += f" (flagged items: {result.flagged_items})"
            summaries.append(summary)

        screening_summary = "\n".join(summaries) if summaries else "No screening results available."

        return self.SYSTEM_PROMPT_TEMPLATE.format(screening_summary=screening_summary)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_conversation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add talker/agents/conversation.py tests/test_conversation.py
git commit -m "feat: conversation agent for screening follow-up dialogue"
```

---

### Task 8: Orchestrator Agent

**Files:**
- Create: `talker/agents/orchestrator.py`
- Test: `tests/test_orchestrator.py`

- [ ] **Step 1: Write tests for orchestrator**

```python
# tests/test_orchestrator.py
import pytest
from talker.agents.orchestrator import Orchestrator, OrchestratorState
from talker.models.schemas import SessionState


def test_orchestrator_initial_state():
    orch = Orchestrator(instruments_dir="talker/instruments")
    assert orch.state == SessionState.CREATED


def test_orchestrator_start_creates_intake():
    orch = Orchestrator(instruments_dir="talker/instruments")
    greeting = orch.start()
    assert orch.state == SessionState.INTAKE
    assert "not a medical" in greeting.lower() or "not a diagnosis" in greeting.lower()


def test_orchestrator_select_instruments():
    orch = Orchestrator(instruments_dir="talker/instruments")
    orch.start()
    orch.select_instruments(["phq-9", "gad-7"])
    assert orch.state == SessionState.SCREENING
    assert len(orch.instrument_queue) == 2


def test_orchestrator_full_checkup():
    orch = Orchestrator(instruments_dir="talker/instruments")
    orch.start()
    orch.select_full_checkup()
    assert orch.state == SessionState.SCREENING
    assert len(orch.instrument_queue) >= 4


def test_orchestrator_state_transitions():
    orch = Orchestrator(instruments_dir="talker/instruments")
    assert orch.state == SessionState.CREATED
    orch.start()
    assert orch.state == SessionState.INTAKE
    orch.select_instruments(["phq-9"])
    assert orch.state == SessionState.SCREENING
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_orchestrator.py -v`
Expected: FAIL

- [ ] **Step 3: Implement Orchestrator**

```python
# talker/agents/orchestrator.py
from talker.agents.conversation import ConversationAgent, ConversationContext
from talker.agents.safety import SafetyMonitor, SafetyInterrupt
from talker.agents.screener import ScreenerAgent
from talker.models.schemas import ScreeningResult, SessionState
from talker.services.instruments import InstrumentLoader


GREETING = """Welcome to Talker, your psychology pre-assessment assistant.

IMPORTANT: This is NOT a medical or diagnostic tool. The results are screening indicators, not diagnoses. Always consult a qualified mental health professional for proper evaluation.

I can help you explore how you've been feeling by walking you through some validated screening questionnaires, followed by a conversation about the results.

Would you like to:
1. Tell me what's been on your mind (I'll suggest relevant screenings)
2. Run a full checkup (all available screenings)
3. Choose specific screenings to take"""


class Orchestrator:
    """Central coordinator for assessment sessions."""

    def __init__(self, instruments_dir: str = "talker/instruments"):
        self.state = SessionState.CREATED
        self.loader = InstrumentLoader(instruments_dir)
        self.screener = ScreenerAgent(self.loader)
        self.conversation = ConversationAgent()
        self.safety = SafetyMonitor()

        self.instrument_queue: list[str] = []
        self.completed_results: list[ScreeningResult] = []
        self.current_instrument_index: int = 0

    def start(self) -> str:
        self.state = SessionState.INTAKE
        return GREETING

    def check_safety(self, text: str) -> SafetyInterrupt | None:
        return self.safety.check(text)

    def select_instruments(self, instrument_ids: list[str]) -> None:
        self.instrument_queue = instrument_ids
        self.current_instrument_index = 0
        self.state = SessionState.SCREENING
        if self.instrument_queue:
            self.screener.start_instrument(self.instrument_queue[0])

    def select_full_checkup(self) -> None:
        all_instruments = self.loader.load_all()
        self.select_instruments([i.metadata.id for i in all_instruments])

    def get_current_screening_question(self) -> dict | None:
        if self.state != SessionState.SCREENING:
            return None
        q = self.screener.get_current_question()
        if q is None:
            return None
        progress_current, progress_total = self.screener.get_progress()
        return {
            "instrument_id": self.instrument_queue[self.current_instrument_index],
            "question": q.text,
            "question_number": progress_current + 1,
            "total_questions": progress_total,
            "response_options": [
                {"label": o.label, "value": o.value}
                for o in self.screener.current_instrument.response_options
            ],
        }

    def submit_screening_answer(self, value: int) -> dict:
        """Submit an answer. Returns status dict with next action."""
        self.screener.record_answer(value)

        if self.screener.is_complete():
            result = self.screener.get_result()
            if result:
                self.completed_results.append(result)

            self.current_instrument_index += 1
            if self.current_instrument_index < len(self.instrument_queue):
                next_id = self.instrument_queue[self.current_instrument_index]
                self.screener.start_instrument(next_id)
                return {"action": "next_instrument", "instrument_id": next_id}
            else:
                self.state = SessionState.FOLLOW_UP
                return {"action": "screening_complete", "results": self.completed_results}

        return {"action": "next_question"}

    def skip_follow_up(self) -> None:
        self.state = SessionState.SUMMARY

    def get_conversation_context(self) -> ConversationContext:
        return ConversationContext(screening_results=self.completed_results)

    def complete(self) -> None:
        self.state = SessionState.COMPLETED
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_orchestrator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add talker/agents/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: orchestrator agent coordinating assessment flow"
```

---

### Task 8b: Tool-Calling — Intake Triage

**Files:**
- Create: `talker/agents/tools.py`
- Test: `tests/test_tools.py`
- Modify: `talker/agents/orchestrator.py`

- [ ] **Step 1: Write tests for intake triage tool**

```python
# tests/test_tools.py
import pytest
from talker.agents.tools import (
    parse_instrument_selection,
    get_score_context,
)
from talker.services.instruments import InstrumentLoader


def test_parse_instrument_selection_valid():
    result = parse_instrument_selection(["phq-9", "gad-7"])
    assert result == ["phq-9", "gad-7"]


def test_parse_instrument_selection_dedupes():
    result = parse_instrument_selection(["phq-9", "phq-9", "gad-7"])
    assert result == ["phq-9", "gad-7"]


def test_parse_instrument_selection_filters_invalid():
    loader = InstrumentLoader("talker/instruments")
    valid_ids = {i.metadata.id for i in loader.load_all()}
    result = parse_instrument_selection(["phq-9", "fake-instrument"], valid_ids=valid_ids)
    assert result == ["phq-9"]


def test_get_score_context_phq9():
    loader = InstrumentLoader("talker/instruments")
    context = get_score_context("phq-9", 14, loader)
    assert "moderate" in context.lower()
    assert "phq-9" in context.lower()


def test_get_score_context_minimal():
    loader = InstrumentLoader("talker/instruments")
    context = get_score_context("phq-9", 2, loader)
    assert "minimal" in context.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tools.py -v`
Expected: FAIL

- [ ] **Step 3: Implement agent tools**

```python
# talker/agents/tools.py
"""Typed tool functions for PydanticAI agents."""

from talker.services.instruments import InstrumentLoader


INSTRUMENT_TRIAGE_PROMPT = """Based on the user's description, select which screening instruments to run.

Available instruments:
{instruments_list}

Analyze the user's concerns and return a JSON list of instrument IDs that are most relevant.
Only select instruments that directly relate to the user's described symptoms.
If unsure, err on the side of including more rather than fewer.

User's description: {user_input}

Return ONLY a JSON array of instrument IDs, e.g. ["phq-9", "gad-7"]"""


def parse_instrument_selection(
    ids: list[str],
    valid_ids: set[str] | None = None,
) -> list[str]:
    """Validate and deduplicate instrument IDs."""
    seen = set()
    result = []
    for id_ in ids:
        id_clean = id_.strip().lower()
        if id_clean in seen:
            continue
        if valid_ids and id_clean not in valid_ids:
            continue
        seen.add(id_clean)
        result.append(id_clean)
    return result


def build_triage_prompt(user_input: str, loader: InstrumentLoader) -> str:
    """Build the prompt for LLM-based instrument selection."""
    instruments = loader.load_all()
    instruments_list = "\n".join(
        f"- {i.metadata.id}: {i.metadata.name} — {i.metadata.description}"
        for i in instruments
    )
    return INSTRUMENT_TRIAGE_PROMPT.format(
        instruments_list=instruments_list,
        user_input=user_input,
    )


def get_score_context(
    instrument_id: str,
    score: int,
    loader: InstrumentLoader,
) -> str:
    """Get human-readable context for a screening score."""
    instrument = loader.load(instrument_id)
    meta = instrument.metadata

    severity = instrument.scoring.thresholds[-1].severity
    for t in instrument.scoring.thresholds:
        if score <= t.max:
            severity = t.severity
            break

    max_score = sum(
        max(o.value for o in instrument.response_options)
        for _ in instrument.questions
    )

    context = (
        f"{meta.name} ({meta.id.upper()})\n"
        f"Your score: {score} out of {max_score}\n"
        f"Severity level: {severity}\n\n"
    )

    thresholds_desc = ", ".join(
        f"{t.severity} (0-{t.max})" for t in instrument.scoring.thresholds
    )
    context += f"Score ranges: {thresholds_desc}\n\n"

    if severity in ("moderate", "moderately severe", "severe", "above threshold"):
        context += (
            f"A score in the {severity} range suggests significant symptoms "
            f"that would benefit from professional evaluation. "
            f"Consider discussing these results with a mental health professional."
        )
    elif severity == "mild":
        context += (
            f"A score in the mild range suggests some symptoms are present. "
            f"Monitoring over time is recommended. If symptoms persist or worsen, "
            f"consider consulting a professional."
        )
    else:
        context += (
            f"A score in the {severity} range suggests minimal symptoms. "
            f"If you're still concerned, a professional consultation can provide clarity."
        )

    return context
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tools.py -v`
Expected: PASS

- [ ] **Step 5: Wire triage tool into Orchestrator**

Add to `talker/agents/orchestrator.py`:

```python
from talker.agents.tools import build_triage_prompt, parse_instrument_selection, get_score_context

# Add method to Orchestrator class:
def get_triage_prompt(self, user_input: str) -> str:
    """Build prompt for LLM to select instruments based on user's intake."""
    return build_triage_prompt(user_input, self.loader)

def select_instruments_from_triage(self, instrument_ids: list[str]) -> None:
    """Select instruments after LLM triage. Validates IDs."""
    valid_ids = {i.metadata.id for i in self.loader.load_all()}
    validated = parse_instrument_selection(instrument_ids, valid_ids)
    if not validated:
        self.select_full_checkup()
    else:
        self.select_instruments(validated)

def get_score_context_for_result(self, instrument_id: str, score: int) -> str:
    """Get interpretation context for a screening score."""
    return get_score_context(instrument_id, score, self.loader)
```

- [ ] **Step 6: Commit**

```bash
git add talker/agents/tools.py tests/test_tools.py talker/agents/orchestrator.py
git commit -m "feat: tool-calling for intake triage and score interpretation"
```

---

## Chunk 3: Web UI

### Task 9: Base Templates & Static Assets

**Files:**
- Create: `talker/templates/base.html`
- Create: `talker/templates/index.html`
- Create: `talker/static/css/style.css`
- Create: `talker/static/js/app.js`
- Create: `talker/routes/__init__.py`
- Create: `talker/routes/main.py`
- Modify: `talker/main.py`

- [ ] **Step 1: Create base HTML template**

```html
<!-- talker/templates/base.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Talker{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', path='css/style.css') }}">
    {% block head %}{% endblock %}
</head>
<body>
    <nav class="navbar">
        <a href="/" class="logo">Talker</a>
        <div class="nav-links">
            <a href="/">Home</a>
            <a href="/history">History</a>
            <a href="/settings">Settings</a>
        </div>
    </nav>
    <main class="container">
        {% block content %}{% endblock %}
    </main>
    <footer class="footer">
        <p>This is NOT a medical or diagnostic tool. Always consult a qualified mental health professional.</p>
    </footer>
    {% block scripts %}{% endblock %}
</body>
</html>
```

- [ ] **Step 2: Create calming CSS stylesheet**

```css
/* talker/static/css/style.css */
:root {
    --bg: #f8f7f4;
    --bg-card: #ffffff;
    --text: #2d3436;
    --text-muted: #636e72;
    --primary: #6c5ce7;
    --primary-light: #a29bfe;
    --accent: #00b894;
    --warning: #fdcb6e;
    --danger: #e17055;
    --border: #dfe6e9;
    --shadow: 0 2px 8px rgba(0,0,0,0.06);
    --radius: 12px;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
}

.container {
    max-width: 720px;
    margin: 0 auto;
    padding: 2rem 1.5rem;
}

.navbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 2rem;
    background: var(--bg-card);
    border-bottom: 1px solid var(--border);
}

.logo {
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--primary);
    text-decoration: none;
}

.nav-links { display: flex; gap: 1.5rem; }
.nav-links a { color: var(--text-muted); text-decoration: none; font-size: 0.9rem; }
.nav-links a:hover { color: var(--primary); }

.footer {
    text-align: center;
    padding: 2rem;
    color: var(--text-muted);
    font-size: 0.8rem;
    border-top: 1px solid var(--border);
    margin-top: 3rem;
}

.card {
    background: var(--bg-card);
    border-radius: var(--radius);
    padding: 1.5rem;
    box-shadow: var(--shadow);
    margin-bottom: 1rem;
}

.btn {
    display: inline-block;
    padding: 0.75rem 1.5rem;
    border-radius: 8px;
    border: none;
    font-size: 1rem;
    cursor: pointer;
    text-decoration: none;
    transition: all 0.2s;
}

.btn-primary { background: var(--primary); color: white; }
.btn-primary:hover { background: var(--primary-light); }
.btn-secondary { background: var(--border); color: var(--text); }
.btn-secondary:hover { background: #b2bec3; }

.btn-option {
    display: block;
    width: 100%;
    padding: 1rem;
    margin-bottom: 0.5rem;
    background: var(--bg-card);
    border: 2px solid var(--border);
    border-radius: 8px;
    text-align: left;
    font-size: 1rem;
    cursor: pointer;
    transition: all 0.2s;
}
.btn-option:hover { border-color: var(--primary); background: #f0effc; }
.btn-option.selected { border-color: var(--primary); background: #f0effc; }

.progress-bar {
    width: 100%;
    height: 6px;
    background: var(--border);
    border-radius: 3px;
    margin: 1rem 0;
}
.progress-bar-fill {
    height: 100%;
    background: var(--primary);
    border-radius: 3px;
    transition: width 0.3s ease;
}

.severity-minimal { color: var(--accent); }
.severity-mild { color: var(--warning); }
.severity-moderate { color: var(--danger); }
.severity-severe { color: #d63031; }

.chat-container { display: flex; flex-direction: column; gap: 1rem; }
.chat-message {
    padding: 0.75rem 1rem;
    border-radius: 12px;
    max-width: 85%;
}
.chat-assistant {
    background: var(--bg-card);
    border: 1px solid var(--border);
    align-self: flex-start;
}
.chat-user {
    background: var(--primary);
    color: white;
    align-self: flex-end;
}

.chat-input-container {
    display: flex;
    gap: 0.5rem;
    margin-top: 1rem;
}
.chat-input {
    flex: 1;
    padding: 0.75rem 1rem;
    border: 2px solid var(--border);
    border-radius: 8px;
    font-size: 1rem;
    outline: none;
}
.chat-input:focus { border-color: var(--primary); }

h1 { font-size: 1.75rem; margin-bottom: 0.5rem; }
h2 { font-size: 1.25rem; margin-bottom: 0.5rem; }
.subtitle { color: var(--text-muted); margin-bottom: 1.5rem; }

.safety-alert {
    background: #ffeaa7;
    border: 2px solid var(--warning);
    border-radius: var(--radius);
    padding: 1.5rem;
    margin: 1rem 0;
}
.safety-alert h3 { color: #d63031; margin-bottom: 0.5rem; }
.safety-alert ul { margin-left: 1.5rem; }
```

- [ ] **Step 3: Create index template**

```html
<!-- talker/templates/index.html -->
{% extends "base.html" %}
{% block title %}Talker — Home{% endblock %}
{% block content %}
<h1>Welcome to Talker</h1>
<p class="subtitle">Your psychology pre-assessment guide</p>

<div class="card">
    <h2>Start a New Assessment</h2>
    <p style="margin-bottom: 1rem; color: var(--text-muted);">
        Walk through validated screening questionnaires followed by a guided conversation
        to help you understand your mental health and prepare for professional consultation.
    </p>
    <a href="/assess" class="btn btn-primary">Begin Assessment</a>
</div>

{% if recent_sessions %}
<div class="card">
    <h2>Recent Sessions</h2>
    {% for session in recent_sessions %}
    <a href="/assess/{{ session.id }}" style="text-decoration:none;color:inherit;">
        <div style="padding: 0.75rem 0; border-bottom: 1px solid var(--border);">
            <span>{{ session.created_at.strftime('%b %d, %Y %H:%M') }}</span>
            <span style="float:right; color: var(--text-muted);">{{ session.state }}</span>
        </div>
    </a>
    {% endfor %}
</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 4: Create main route**

```python
# talker/routes/__init__.py
```

```python
# talker/routes/main.py
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="talker/templates")
router = APIRouter()


@router.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"recent_sessions": []},
    )
```

- [ ] **Step 5: Update main.py to include routes and static files**

```python
# talker/main.py
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from talker.config import Settings
from talker.routes.main import router as main_router


@lru_cache
def get_settings() -> Settings:
    return Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Talker", lifespan=lifespan)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(main_router)
```

- [ ] **Step 6: Create empty js file**

```javascript
// talker/static/js/app.js
// Main application JavaScript
```

- [ ] **Step 7: Verify the app starts and serves the page**

Run: `uv run uvicorn talker.main:app --reload --port 8000`
Visit: http://localhost:8000 — should show the home page with calming design.

- [ ] **Step 8: Commit**

```bash
git add talker/templates/ talker/static/ talker/routes/ talker/main.py
git commit -m "feat: base templates, calming CSS, and home page"
```

---

### Task 10: Assessment Flow UI

**Files:**
- Create: `talker/templates/assess.html`
- Create: `talker/templates/assess_screening.html`
- Create: `talker/templates/assess_conversation.html`
- Create: `talker/templates/assess_summary.html`
- Create: `talker/routes/assess.py`
- Modify: `talker/main.py` (add router)

- [ ] **Step 1: Create assessment start page**

```html
<!-- talker/templates/assess.html -->
{% extends "base.html" %}
{% block title %}Talker — Assessment{% endblock %}
{% block content %}
<h1>New Assessment</h1>
<p class="subtitle">Choose how you'd like to start</p>

<form method="post" action="/assess/start">
    <div class="card">
        <h2>Select Screenings</h2>
        <p style="color:var(--text-muted);margin-bottom:1rem;">Choose specific areas to screen, or run a full checkup.</p>

        {% for instrument in instruments %}
        <label class="btn-option" style="display:flex;align-items:center;gap:0.75rem;">
            <input type="checkbox" name="instruments" value="{{ instrument.id }}" style="width:18px;height:18px;">
            <div>
                <strong>{{ instrument.name }}</strong>
                <br><small style="color:var(--text-muted);">{{ instrument.description }} ({{ instrument.item_count }} questions)</small>
            </div>
        </label>
        {% endfor %}

        <div style="display:flex;gap:1rem;margin-top:1.5rem;">
            <button type="submit" class="btn btn-primary">Start Selected</button>
            <button type="submit" name="full_checkup" value="1" class="btn btn-secondary">Full Checkup</button>
        </div>
    </div>
</form>
{% endblock %}
```

- [ ] **Step 2: Create screening question page**

```html
<!-- talker/templates/assess_screening.html -->
{% extends "base.html" %}
{% block title %}Talker — Screening{% endblock %}
{% block content %}
<h2>{{ instrument_name }}</h2>
<p class="subtitle">Question {{ question_number }} of {{ total_questions }}</p>

<div class="progress-bar">
    <div class="progress-bar-fill" style="width: {{ (question_number / total_questions * 100)|int }}%"></div>
</div>

<div class="card">
    <p style="font-size:1.1rem;margin-bottom:1.5rem;line-height:1.5;">
        Over the last 2 weeks, how often have you been bothered by:<br>
        <strong>{{ question_text }}</strong>
    </p>

    <form method="post" action="/assess/answer">
        <input type="hidden" name="session_id" value="{{ session_id }}">
        {% for option in response_options %}
        <button type="submit" name="value" value="{{ option.value }}" class="btn-option">
            {{ option.label }}
        </button>
        {% endfor %}
    </form>
</div>
{% endblock %}
```

- [ ] **Step 3: Create conversation page**

```html
<!-- talker/templates/assess_conversation.html -->
{% extends "base.html" %}
{% block title %}Talker — Conversation{% endblock %}
{% block content %}
<h2>Follow-up Conversation</h2>
<p class="subtitle">Let's explore your results together</p>

<div class="card">
    <div class="chat-container" id="chat">
        {% for msg in messages %}
        <div class="chat-message {{ 'chat-assistant' if msg.role == 'assistant' else 'chat-user' }}">
            {{ msg.content }}
        </div>
        {% endfor %}
    </div>

    <form method="post" action="/assess/chat" class="chat-input-container">
        <input type="hidden" name="session_id" value="{{ session_id }}">
        <input type="text" name="message" class="chat-input" placeholder="Type your response..." autofocus>
        <button type="submit" class="btn btn-primary">Send</button>
    </form>

    <div style="margin-top:1rem;text-align:center;">
        <a href="/assess/summary?session_id={{ session_id }}" class="btn btn-secondary">Skip to Summary</a>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 4: Create summary page**

```html
<!-- talker/templates/assess_summary.html -->
{% extends "base.html" %}
{% block title %}Talker — Summary{% endblock %}
{% block content %}
<h1>Assessment Summary</h1>
<p class="subtitle">Here's what we found</p>

{% for result in results %}
<div class="card">
    <h2>{{ result.instrument_id | upper }}</h2>
    <p>
        Score: <strong>{{ result.score }}</strong> —
        <span class="severity-{{ result.severity | replace(' ', '-') }}">{{ result.severity }}</span>
    </p>
    {% if result.flagged_items %}
    <p style="color:var(--danger);margin-top:0.5rem;">Flagged items: {{ result.flagged_items | join(', ') }}</p>
    {% endif %}
</div>
{% endfor %}

<div class="card">
    <h2>Recommendations</h2>
    <ul style="margin-left:1.5rem;">
        {% for rec in recommendations %}
        <li>{{ rec }}</li>
        {% endfor %}
    </ul>
</div>

<div class="card" style="text-align:center;">
    <a href="/" class="btn btn-primary">Return Home</a>
    <a href="/report/{{ session_id }}" class="btn btn-secondary" style="margin-left:0.5rem;">Download Report</a>
</div>
{% endblock %}
```

- [ ] **Step 5: Create assessment routes**

```python
# talker/routes/assess.py
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from talker.agents.orchestrator import Orchestrator
from talker.services.instruments import InstrumentLoader

templates = Jinja2Templates(directory="talker/templates")
router = APIRouter(prefix="/assess")

# In-memory session store for MVP. Replace with DB-backed sessions later.
_sessions: dict[str, Orchestrator] = {}
_session_counter = 0
_chat_histories: dict[str, list[dict]] = {}


def _new_session_id() -> str:
    global _session_counter
    _session_counter += 1
    return str(_session_counter)


@router.get("")
async def assess_start(request: Request):
    loader = InstrumentLoader("talker/instruments")
    instruments = loader.load_all()
    metas = [i.metadata for i in instruments]
    return templates.TemplateResponse(
        request=request,
        name="assess.html",
        context={"instruments": metas},
    )


@router.post("/start")
async def assess_begin(
    request: Request,
    instruments: list[str] = Form(default=[]),
    full_checkup: str = Form(default=""),
):
    session_id = _new_session_id()
    orch = Orchestrator()
    orch.start()

    if full_checkup:
        orch.select_full_checkup()
    elif instruments:
        orch.select_instruments(instruments)
    else:
        orch.select_full_checkup()

    _sessions[session_id] = orch
    return RedirectResponse(url=f"/assess/screening?session_id={session_id}", status_code=303)


@router.get("/screening")
async def assess_screening(request: Request, session_id: str):
    orch = _sessions.get(session_id)
    if not orch:
        return RedirectResponse(url="/assess")

    question_data = orch.get_current_screening_question()
    if not question_data:
        return RedirectResponse(url=f"/assess/conversation?session_id={session_id}")

    loader = InstrumentLoader("talker/instruments")
    instrument = loader.load(question_data["instrument_id"])

    return templates.TemplateResponse(
        request=request,
        name="assess_screening.html",
        context={
            "session_id": session_id,
            "instrument_name": instrument.metadata.name,
            "question_text": question_data["question"],
            "question_number": question_data["question_number"],
            "total_questions": question_data["total_questions"],
            "response_options": question_data["response_options"],
        },
    )


@router.post("/answer")
async def assess_answer(
    request: Request,
    session_id: str = Form(),
    value: int = Form(),
):
    orch = _sessions.get(session_id)
    if not orch:
        return RedirectResponse(url="/assess")

    result = orch.submit_screening_answer(value)

    if result["action"] == "screening_complete":
        return RedirectResponse(url=f"/assess/conversation?session_id={session_id}", status_code=303)

    return RedirectResponse(url=f"/assess/screening?session_id={session_id}", status_code=303)


@router.get("/conversation")
async def assess_conversation(request: Request, session_id: str):
    orch = _sessions.get(session_id)
    if not orch:
        return RedirectResponse(url="/assess")

    messages = _chat_histories.get(session_id, [])
    if not messages:
        # Initial message from assistant
        ctx = orch.get_conversation_context()
        intro = "Thank you for completing the screenings. I'd like to learn more about how you've been feeling. "
        if orch.completed_results:
            intro += "Based on your responses, I have a few areas I'd like to explore with you. How are you doing right now?"
        messages = [{"role": "assistant", "content": intro}]
        _chat_histories[session_id] = messages

    return templates.TemplateResponse(
        request=request,
        name="assess_conversation.html",
        context={"session_id": session_id, "messages": messages},
    )


@router.post("/chat")
async def assess_chat(
    request: Request,
    session_id: str = Form(),
    message: str = Form(),
):
    orch = _sessions.get(session_id)
    if not orch:
        return RedirectResponse(url="/assess")

    messages = _chat_histories.get(session_id, [])
    messages.append({"role": "user", "content": message})

    # Safety check
    safety_result = orch.check_safety(message)
    if safety_result:
        safety_msg = safety_result.message + "\n\n" + "\n".join(f"- {r}" for r in safety_result.resources)
        messages.append({"role": "assistant", "content": safety_msg})
        _chat_histories[session_id] = messages
        return RedirectResponse(url=f"/assess/conversation?session_id={session_id}", status_code=303)

    # TODO: Integrate LLM call here. For now, static response.
    messages.append({
        "role": "assistant",
        "content": "Thank you for sharing that. Could you tell me more about how this has been affecting your daily life?",
    })
    _chat_histories[session_id] = messages

    return RedirectResponse(url=f"/assess/conversation?session_id={session_id}", status_code=303)


@router.get("/summary")
async def assess_summary(request: Request, session_id: str):
    orch = _sessions.get(session_id)
    if not orch:
        return RedirectResponse(url="/assess")

    orch.skip_follow_up()
    results = orch.completed_results

    recommendations = []
    for r in results:
        if r.severity in ("moderate", "moderately severe", "severe", "above threshold"):
            recommendations.append(
                f"Your {r.instrument_id.upper()} score ({r.score}) suggests {r.severity} symptoms. "
                f"Consider consulting a mental health professional about this area."
            )
        if r.flagged_items:
            recommendations.append(
                f"Some responses on {r.instrument_id.upper()} were flagged for follow-up."
            )

    if not recommendations:
        recommendations.append(
            "Your screening scores are in the minimal/mild range. "
            "If you're still concerned, a professional consultation can provide more clarity."
        )

    orch.complete()

    return templates.TemplateResponse(
        request=request,
        name="assess_summary.html",
        context={
            "session_id": session_id,
            "results": results,
            "recommendations": recommendations,
        },
    )
```

- [ ] **Step 6: Add assess router to main.py**

Add to `talker/main.py` after the main_router import:
```python
from talker.routes.assess import router as assess_router
# ...
app.include_router(assess_router)
```

- [ ] **Step 7: Manual test — full assessment flow**

Run: `uv run uvicorn talker.main:app --reload --port 8000`
1. Visit http://localhost:8000 — click "Begin Assessment"
2. Select PHQ-9 and GAD-7 — click "Start Selected"
3. Answer all questions — verify progress bar advances
4. Reach conversation page — type a message, see response
5. Click "Skip to Summary" — verify scores and recommendations display

- [ ] **Step 8: Commit**

```bash
git add talker/templates/ talker/routes/assess.py talker/main.py
git commit -m "feat: complete assessment flow UI (screening, conversation, summary)"
```

---

### Task 11: LLM-Powered Conversation Integration

**Files:**
- Modify: `talker/routes/assess.py` (replace static chat response with LLM call)
- Modify: `talker/main.py` (initialize services in lifespan)

- [ ] **Step 1: Update main.py lifespan to initialize LLM and tracing**

```python
# In talker/main.py, update lifespan:
from talker.services.tracing import init_langfuse

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_langfuse(settings)
    yield
```

- [ ] **Step 2: Add PydanticAI conversation agent to assess routes**

Replace the `# TODO: Integrate LLM call here` block in `talker/routes/assess.py`:

```python
# Add imports at top of assess.py:
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from talker.config import Settings
from talker.main import get_settings

# Replace the chat endpoint's TODO block with:
async def _get_llm_response(orch: Orchestrator, messages: list[dict], user_message: str) -> str:
    """Get LLM response for conversation."""
    settings = get_settings()
    if not settings.openrouter_api_key:
        return "Thank you for sharing that. Could you tell me more about how this has been affecting your daily life?"

    ctx = orch.get_conversation_context()
    system_prompt = orch.conversation.build_system_prompt(ctx)

    model = OpenAIChatModel(
        settings.openrouter_model_conversation,
        provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
    )
    agent = Agent(model, system_prompt=system_prompt)

    # Build message history for context
    history_text = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
        for m in messages[-10:]  # Last 10 messages for context
    )

    result = await agent.run(f"Conversation so far:\n{history_text}\n\nUser: {user_message}")
    return result.output
```

Update the `assess_chat` function to call `_get_llm_response` instead of the static message:

```python
    # Replace the static response with:
    response = await _get_llm_response(orch, messages, message)
    messages.append({"role": "assistant", "content": response})
```

- [ ] **Step 3: Manual test with OpenRouter API key**

Set `OPENROUTER_API_KEY` in `.env`, then test the conversation flow. Verify:
- LLM responds contextually to screening results
- Conversation feels natural and exploratory
- Without API key, falls back to static response

- [ ] **Step 4: Commit**

```bash
git add talker/routes/assess.py talker/main.py
git commit -m "feat: LLM-powered conversation using PydanticAI + OpenRouter"
```

---

### Task 12: Session History & Persistence

**Files:**
- Create: `talker/templates/history.html`
- Create: `talker/templates/session_detail.html`
- Create: `talker/routes/history.py`
- Modify: `talker/main.py` (add router, wire up DB)
- Modify: `talker/routes/assess.py` (persist to DB)

- [ ] **Step 1: Create history template**

```html
<!-- talker/templates/history.html -->
{% extends "base.html" %}
{% block title %}Talker — History{% endblock %}
{% block content %}
<h1>Session History</h1>
<p class="subtitle">Your past assessments</p>

{% if sessions %}
    {% for session in sessions %}
    <a href="/history/{{ session.id }}" style="text-decoration:none;color:inherit;">
        <div class="card" style="display:flex;justify-content:space-between;align-items:center;">
            <div>
                <strong>{{ session.created_at.strftime('%B %d, %Y at %H:%M') }}</strong>
                <br><small style="color:var(--text-muted);">
                    {{ session.screenings | length }} screening(s) — {{ session.state }}
                </small>
            </div>
            <div style="text-align:right;">
                {% for s in session.screenings %}
                <span class="severity-{{ s.severity | replace(' ', '-') }}" style="font-size:0.85rem;">
                    {{ s.instrument_id | upper }}: {{ s.severity }}
                </span><br>
                {% endfor %}
            </div>
        </div>
    </a>
    {% endfor %}
{% else %}
    <div class="card">
        <p style="color:var(--text-muted);text-align:center;">No sessions yet. <a href="/assess">Start your first assessment.</a></p>
    </div>
{% endif %}
{% endblock %}
```

- [ ] **Step 2: Create session detail template**

```html
<!-- talker/templates/session_detail.html -->
{% extends "base.html" %}
{% block title %}Talker — Session {{ session.id }}{% endblock %}
{% block content %}
<h1>Session {{ session.id }}</h1>
<p class="subtitle">{{ session.created_at.strftime('%B %d, %Y at %H:%M') }} — {{ session.state }}</p>

{% for screening in session.screenings %}
<div class="card">
    <h2>{{ screening.instrument_id | upper }}</h2>
    <p>
        Score: <strong>{{ screening.score }}</strong> —
        <span class="severity-{{ screening.severity | replace(' ', '-') }}">{{ screening.severity }}</span>
    </p>
    {% if screening.flagged_items %}
    <p style="color:var(--danger);">Flagged items: {{ screening.flagged_items | join(', ') }}</p>
    {% endif %}
</div>
{% endfor %}

{% if session.conversations %}
<div class="card">
    <h2>Conversation Notes</h2>
    {% for conv in session.conversations %}
        {% for obs in conv.observations %}
        <p style="margin-bottom:0.5rem;"><strong>{{ obs.topic }}:</strong> {{ obs.observation }}</p>
        {% endfor %}
    {% endfor %}
</div>
{% endif %}

<div style="text-align:center;margin-top:1rem;">
    <a href="/history" class="btn btn-secondary">Back to History</a>
</div>
{% endblock %}
```

- [ ] **Step 3: Create history routes**

```python
# talker/routes/history.py
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="talker/templates")
router = APIRouter(prefix="/history")


@router.get("")
async def history_list(request: Request):
    # TODO: Query from database. For now, empty list.
    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={"sessions": []},
    )


@router.get("/{session_id}")
async def history_detail(request: Request, session_id: int):
    # TODO: Query from database.
    return RedirectResponse(url="/history")
```

- [ ] **Step 4: Wire up database in main.py lifespan and add history router**

```python
# Update talker/main.py:
from talker.routes.history import router as history_router
from talker.services.database import create_session_factory

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_langfuse(settings)
    app.state.db_session_factory = create_session_factory(settings)
    yield

# After other router includes:
app.include_router(history_router)
```

- [ ] **Step 5: Commit**

```bash
git add talker/templates/history.html talker/templates/session_detail.html talker/routes/history.py talker/main.py
git commit -m "feat: session history pages and database wiring"
```

---

### Task 13: Settings Page

**Files:**
- Create: `talker/templates/settings.html`
- Create: `talker/routes/settings.py`
- Modify: `talker/main.py` (add router)

- [ ] **Step 1: Create settings template**

```html
<!-- talker/templates/settings.html -->
{% extends "base.html" %}
{% block title %}Talker — Settings{% endblock %}
{% block content %}
<h1>Settings</h1>
<p class="subtitle">Configure your Talker experience</p>

<div class="card">
    <h2>Service Status</h2>
    <div style="display:grid;gap:0.5rem;margin-top:0.75rem;">
        <div style="display:flex;justify-content:space-between;">
            <span>OpenRouter LLM</span>
            <span style="color: {{ 'var(--accent)' if openrouter_configured else 'var(--danger)' }};">
                {{ 'Connected' if openrouter_configured else 'Not configured' }}
            </span>
        </div>
        <div style="display:flex;justify-content:space-between;">
            <span>Langfuse Tracing</span>
            <span style="color: {{ 'var(--accent)' if langfuse_configured else 'var(--text-muted)' }};">
                {{ 'Connected' if langfuse_configured else 'Not configured (optional)' }}
            </span>
        </div>
        <div style="display:flex;justify-content:space-between;">
            <span>Database</span>
            <span style="color: {{ 'var(--accent)' if db_connected else 'var(--danger)' }};">
                {{ 'Connected' if db_connected else 'Disconnected' }}
            </span>
        </div>
    </div>
</div>

<div class="card">
    <h2>Models</h2>
    <p style="color:var(--text-muted);margin-bottom:0.5rem;">Current model configuration (set via environment variables)</p>
    <div style="display:grid;gap:0.5rem;">
        <div><strong>Conversation:</strong> {{ conversation_model }}</div>
        <div><strong>Screener:</strong> {{ screener_model }}</div>
    </div>
</div>

<div class="card">
    <h2>Loaded Instruments</h2>
    <ul style="margin-left:1.5rem;">
        {% for inst in instruments %}
        <li>{{ inst.name }} ({{ inst.item_count }} items)</li>
        {% endfor %}
    </ul>
</div>
{% endblock %}
```

- [ ] **Step 2: Create settings route**

```python
# talker/routes/settings.py
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from talker.config import Settings
from talker.main import get_settings
from talker.services.instruments import InstrumentLoader

templates = Jinja2Templates(directory="talker/templates")
router = APIRouter()


@router.get("/settings")
async def settings_page(request: Request):
    settings = get_settings()
    loader = InstrumentLoader("talker/instruments")
    instruments = [i.metadata for i in loader.load_all()]

    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={
            "openrouter_configured": bool(settings.openrouter_api_key),
            "langfuse_configured": bool(settings.langfuse_secret_key),
            "db_connected": True,  # TODO: actual health check
            "conversation_model": settings.openrouter_model_conversation,
            "screener_model": settings.openrouter_model_screener,
            "instruments": instruments,
        },
    )
```

- [ ] **Step 3: Add settings router to main.py**

```python
from talker.routes.settings import router as settings_router
app.include_router(settings_router)
```

- [ ] **Step 4: Commit**

```bash
git add talker/templates/settings.html talker/routes/settings.py talker/main.py
git commit -m "feat: settings page with service status and configuration"
```

---

### Task 14: Run All Tests & Final Verification

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: Run linter**

Run: `uv run ruff check talker/ tests/`
Expected: No errors (fix any issues)

- [ ] **Step 3: Full manual integration test**

Run: `uv run uvicorn talker.main:app --reload --port 8000`

Verify:
1. Home page loads with calming design
2. "Begin Assessment" → instrument selection page
3. Select PHQ-9 → answer all 9 questions → progress bar works
4. Conversation page loads → type messages → get responses
5. "Skip to Summary" → see scores and recommendations
6. History page loads (empty for now)
7. Settings page shows service status and loaded instruments
8. Safety: type "I want to kill myself" in conversation → crisis resources shown

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: Phase 1 MVP complete — text-based assessment with screening and conversation"
```
