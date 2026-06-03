"""Export session data as CSV / JSON / PDF."""
from __future__ import annotations

import csv
import io
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import AlertEvent, MonitorSession, Reading, User

router = APIRouter(prefix="/api/export", tags=["export"])


def _load(db: Session, session_id: str) -> tuple[list[Reading], list[AlertEvent]]:
    if not db.get(MonitorSession, session_id):
        raise HTTPException(404, "Session not found")
    readings = (
        db.query(Reading).filter(Reading.session_id == session_id).order_by(Reading.ts.asc()).all()
    )
    alerts = (
        db.query(AlertEvent).filter(AlertEvent.session_id == session_id)
        .order_by(AlertEvent.ts.asc()).all()
    )
    return readings, alerts


@router.get("/{session_id}.csv")
def export_csv(
    session_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    readings, _ = _load(db, session_id)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["timestamp", "t_min", "t_max", "t_mean", "roi_mean", "ambient"])
    for r in readings:
        writer.writerow([r.ts.isoformat(), r.t_min, r.t_max, r.t_mean, r.roi_mean, r.ambient])
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=session_{session_id}.csv"},
    )


@router.get("/{session_id}.json")
def export_json(
    session_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    readings, alerts = _load(db, session_id)
    payload = {
        "session_id": session_id,
        "readings": [
            {"ts": r.ts.isoformat(), "t_min": r.t_min, "t_max": r.t_max, "t_mean": r.t_mean,
             "roi_mean": r.roi_mean, "ambient": r.ambient}
            for r in readings
        ],
        "alerts": [
            {"ts": a.ts.isoformat(), "level": a.level, "code": a.code, "message": a.message,
             "value": a.value}
            for a in alerts
        ],
    }
    return Response(json.dumps(payload, indent=2), media_type="application/json")


@router.get("/{session_id}.pdf")
def export_pdf(
    session_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Render a simple session report PDF via reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as pdfcanvas

    readings, alerts = _load(db, session_id)
    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=A4)
    width, height = A4
    y = height - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "ThermoBaby — Reporte de sesion")
    c.setFont("Helvetica", 10)
    y -= 24
    c.drawString(50, y, f"Sesion: {session_id}")
    y -= 18
    if readings:
        tmax = max(r.t_max for r in readings)
        tmin = min(r.t_min for r in readings)
        tmean = sum(r.t_mean for r in readings) / len(readings)
        c.drawString(50, y, f"Lecturas: {len(readings)}  max={tmax:.1f}C  "
                            f"min={tmin:.1f}C  prom={tmean:.1f}C")
        y -= 18
    c.drawString(50, y, f"Alertas: {len(alerts)}")
    y -= 24
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Eventos de alerta")
    c.setFont("Helvetica", 9)
    y -= 16
    for a in alerts[:40]:
        if y < 60:
            c.showPage()
            y = height - 50
        c.drawString(50, y, f"{a.ts.isoformat()}  [{a.level.upper()}] {a.message} ({a.value:.1f}C)")
        y -= 14
    c.showPage()
    c.save()
    buf.seek(0)
    return Response(
        buf.read(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=session_{session_id}.pdf"},
    )
