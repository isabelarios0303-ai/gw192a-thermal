"""Patient (baby) profile CRUD. Scoped to the authenticated owner."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import Patient, User
from app.schemas import PatientCreate, PatientOut

router = APIRouter(prefix="/api/patients", tags=["patients"])


@router.get("", response_model=list[PatientOut])
def list_patients(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    return db.query(Patient).filter(Patient.owner_id == user.id).all()


@router.post("", response_model=PatientOut, status_code=201)
def create_patient(
    payload: PatientCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    patient = Patient(owner_id=user.id, **payload.model_dump())
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def _owned(db: Session, user: User, patient_id: str) -> Patient:
    patient = db.get(Patient, patient_id)
    if not patient or patient.owner_id != user.id:
        raise HTTPException(404, "Patient not found")
    return patient


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(
    patient_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    return _owned(db, user, patient_id)


@router.delete("/{patient_id}", status_code=204)
def delete_patient(
    patient_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    patient = _owned(db, user, patient_id)
    db.delete(patient)
    db.commit()
