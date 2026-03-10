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
