import uuid as uuid_mod
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


class ChatMessage(BaseModel):
    role: str
    content: str


class SessionData(BaseModel):
    """Full in-flight session state loaded from DB."""

    id: uuid_mod.UUID
    state: SessionState
    instrument_queue: list[str] = Field(default_factory=list)
    current_instrument_index: int = 0
    completed_results: list[ScreeningResult] = Field(default_factory=list)
    chat_messages: list[ChatMessage] = Field(default_factory=list)
    current_answers: dict[str, int] = Field(default_factory=dict)
    created_at: datetime


class SessionListItem(BaseModel):
    """Summary for history list page."""

    id: uuid_mod.UUID
    state: str
    created_at: datetime
    completed_at: datetime | None = None
    instruments: list[str] = Field(default_factory=list)
    top_severity: str | None = None
