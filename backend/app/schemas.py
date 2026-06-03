"""Pydantic DTOs for the REST API and WebSocket messages."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# --- auth ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = ""
    role: str = "caregiver"


class UserOut(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: str

    class Config:
        from_attributes = True


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


# --- patients ---
class PatientCreate(BaseModel):
    name: str
    birth_date: str | None = None
    notes: str = ""


class PatientOut(BaseModel):
    id: str
    name: str
    birth_date: str | None
    notes: str
    created_at: datetime

    class Config:
        from_attributes = True


# --- sessions ---
class ROIModel(BaseModel):
    id: str
    name: str
    x0: float
    y0: float
    x1: float
    y1: float
    locked: bool = False
    normalized: bool = True


class SessionCreate(BaseModel):
    patient_id: str
    palette: str = "medical"
    mode: str = "thermal"
    rois: list[ROIModel] = Field(default_factory=list)


class SessionOut(BaseModel):
    id: str
    patient_id: str
    started_at: datetime
    ended_at: datetime | None
    palette: str
    mode: str

    class Config:
        from_attributes = True


# --- websocket processed-frame message ---
class StatsModel(BaseModel):
    t_min: float
    t_max: float
    t_mean: float
    t_std: float
    hotspot: list[int]
    coldspot: list[int]
    centroid: list[float]
    histogram: list[int]
    hist_lo: float
    hist_hi: float


class AlertModel(BaseModel):
    level: str
    code: str
    message: str
    value: float


class ProcessedFrame(BaseModel):
    seq: int
    ts: int
    geometry: str
    palette: str
    stats: StatsModel
    rois: list[dict]
    alerts: list[AlertModel]
    image_png_b64: str | None = None
