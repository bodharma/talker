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
