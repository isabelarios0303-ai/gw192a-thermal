"""Monitoring session lifecycle + history (readings, alerts)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import AlertEvent, MonitorSession, Patient, Reading, User
from app.schemas import SessionCreate, SessionOut

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _owned_patient(db: Session, user: User, patient_id: str) -> Patient:
    patient = db.get(Patient, patient_id)
    if not patient or patient.owner_id != user.id:
        raise HTTPException(404, "Patient not found")
    return patient


@router.post("", response_model=SessionOut, status_code=201)
def start_session(
    payload: SessionCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    _owned_patient(db, user, payload.patient_id)
    session = MonitorSession(
        patient_id=payload.patient_id,
        palette=payload.palette,
        mode=payload.mode,
        rois=[r.model_dump() for r in payload.rois],
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.post("/{session_id}/end", response_model=SessionOut)
def end_session(
    session_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    session = db.get(MonitorSession, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    session.ended_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session


@router.get("/{session_id}/readings")
def session_readings(
    session_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = 1000,
):
    rows = (
        db.query(Reading)
        .filter(Reading.session_id == session_id)
        .order_by(Reading.ts.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            "ts": r.ts.isoformat(),
            "t_min": r.t_min,
            "t_max": r.t_max,
            "t_mean": r.t_mean,
            "roi_mean": r.roi_mean,
            "ambient": r.ambient,
        }
        for r in rows
    ]


@router.get("/{session_id}/alerts")
def session_alerts(
    session_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    rows = (
        db.query(AlertEvent)
        .filter(AlertEvent.session_id == session_id)
        .order_by(AlertEvent.ts.desc())
        .all()
    )
    return [
        {"ts": a.ts.isoformat(), "level": a.level, "code": a.code,
         "message": a.message, "value": a.value}
        for a in rows
    ]
