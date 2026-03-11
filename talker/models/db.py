import uuid as uuid_mod
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(AsyncAttrs, DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), default="default")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_mod.uuid4
    )
    state: Mapped[str] = mapped_column(String(50), default="created")
    mode: Mapped[str] = mapped_column(String(20), default="web")
    instrument_queue: Mapped[list] = mapped_column(JSONB, default=list)
    current_instrument_index: Mapped[int] = mapped_column(Integer, default=0)
    current_answers: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    admin_notes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    screenings: Mapped[list["SessionScreening"]] = relationship(
        back_populates="session", order_by="SessionScreening.created_at"
    )
    conversations: Mapped[list["SessionConversation"]] = relationship(
        back_populates="session", order_by="SessionConversation.created_at"
    )
    summary: Mapped["SessionSummaryRecord | None"] = relationship(back_populates="session")
    safety_events: Mapped[list["SafetyEventRecord"]] = relationship(back_populates="session")
    voice_features: Mapped[list["VoiceFeature"]] = relationship(
        back_populates="session", order_by="VoiceFeature.created_at"
    )


class SessionScreening(Base):
    __tablename__ = "session_screenings"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id")
    )
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
    session_id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id")
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    session: Mapped["Session"] = relationship(back_populates="conversations")


class SessionSummaryRecord(Base):
    __tablename__ = "session_summaries"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id"), unique=True
    )
    instruments_completed: Mapped[list] = mapped_column(JSONB, default=list)
    recommendations: Mapped[list] = mapped_column(JSONB, default=list)
    areas_to_explore: Mapped[list] = mapped_column(JSONB, default=list)
    observations: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    session: Mapped["Session"] = relationship(back_populates="summary")


class SafetyEventRecord(Base):
    __tablename__ = "safety_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id")
    )
    trigger: Mapped[str] = mapped_column(String(255))
    agent: Mapped[str] = mapped_column(String(50))
    message_shown: Mapped[str] = mapped_column(Text)
    resources_provided: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    session: Mapped["Session"] = relationship(back_populates="safety_events")


class VoiceFeature(Base):
    __tablename__ = "voice_features"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id")
    )
    utterance_index: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(20), default="user")
    features: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    session: Mapped["Session"] = relationship(back_populates="voice_features")
