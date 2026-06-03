"""Database models: users, patients (babies), sessions, readings, alerts, snapshots."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), default="")
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="caregiver")  # admin|caregiver|viewer
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    patients: Mapped[list["Patient"]] = relationship(back_populates="owner")


class Patient(Base):
    """A monitored baby/infant profile."""

    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    birth_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    owner: Mapped[User] = relationship(back_populates="patients")
    sessions: Mapped[list["MonitorSession"]] = relationship(back_populates="patient")


class MonitorSession(Base):
    """A continuous monitoring session for a patient."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    palette: Mapped[str] = mapped_column(String(32), default="medical")
    mode: Mapped[str] = mapped_column(String(16), default="thermal")  # rgb|thermal|fusion
    rois: Mapped[dict] = mapped_column(JSON, default=dict)

    patient: Mapped[Patient] = relationship(back_populates="sessions")
    readings: Mapped[list["Reading"]] = relationship(back_populates="session")
    alerts: Mapped[list["AlertEvent"]] = relationship(back_populates="session")


class Reading(Base):
    """A periodic snapshot of statistics (downsampled from the frame stream)."""

    __tablename__ = "readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    t_min: Mapped[float] = mapped_column(Float)
    t_max: Mapped[float] = mapped_column(Float)
    t_mean: Mapped[float] = mapped_column(Float)
    roi_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    ambient: Mapped[float | None] = mapped_column(Float, nullable=True)

    session: Mapped[MonitorSession] = relationship(back_populates="readings")


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    level: Mapped[str] = mapped_column(String(16))   # warning|critical
    code: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(String(255))
    value: Mapped[float] = mapped_column(Float)

    session: Mapped[MonitorSession] = relationship(back_populates="alerts")


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    path: Mapped[str] = mapped_column(String(512))
    kind: Mapped[str] = mapped_column(String(16), default="png")  # png|recording
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
