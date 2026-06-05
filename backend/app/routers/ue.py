"""
Router : consultation des UE.

GET /ue            → liste des UE de la coop de l'utilisateur connecté
GET /ue/{ue_uuid}  → détail d'une UE

Toujours scopé par user_ref1 (du token) — cloisonnement par coop.
"""

import uuid as uuid_lib

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_active_user_ref1, get_current_user
from app.models.ue import Ue
from app.models.user import User
from app.schemas.ue import UeEditResultOut, UeOut, UePatchIn, UeValidationOut
from app.services import ue_edit_service, validation_service

router = APIRouter(prefix="/ue", tags=["ue"])


@router.get("/", response_model=list[UeOut])
def list_ue(
    year_suffix: str | None = None,
    include_inactive: bool = False,
    user_ref1: str = Depends(get_active_user_ref1),
    db: Session = Depends(get_db),
):
    """Liste les UE de la coop. Filtre optionnel par année."""
    q = db.query(Ue).filter(Ue.user_ref1 == user_ref1)
    if year_suffix:
        q = q.filter(Ue.year_suffix == year_suffix)
    if not include_inactive:
        q = q.filter(Ue.is_active.is_(True))
    return q.order_by(Ue.year_suffix, Ue.unite_d_echantillonnage_ue).limit(500).all()


@router.get("/{ue_uuid}", response_model=UeOut)
def get_ue(
    ue_uuid: uuid_lib.UUID,
    user_ref1: str = Depends(get_active_user_ref1),
    db: Session = Depends(get_db),
):
    """Détail d'une UE (de la coop de l'utilisateur)."""
    ue = (
        db.query(Ue)
        .filter(Ue.ue_uuid == ue_uuid, Ue.user_ref1 == user_ref1)
        .first()
    )
    if ue is None:
        raise HTTPException(status_code=404, detail="UE introuvable")
    return ue


@router.get("/{ue_uuid}/validation", response_model=UeValidationOut)
def validate_ue(
    ue_uuid: uuid_lib.UUID,
    user_ref1: str = Depends(get_active_user_ref1),
    db: Session = Depends(get_db),
):
    """
    Juge de complétude d'une UE : liste les champs obligatoires manquants
    (requis + conditionnels activés) et calcule le statut. Lecture seule.
    """
    ue = (
        db.query(Ue)
        .filter(Ue.ue_uuid == ue_uuid, Ue.user_ref1 == user_ref1)
        .first()
    )
    if ue is None:
        raise HTTPException(status_code=404, detail="UE introuvable")
    return validation_service.validate_ue(db, ue)


@router.patch("/{ue_uuid}", response_model=UeEditResultOut)
def patch_ue(
    ue_uuid: uuid_lib.UUID,
    body: UePatchIn,
    user_ref1: str = Depends(get_active_user_ref1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Édite les champs manuels d'une UE (saisie web). Valide les bornes, re-dérive
    traitement si code_dica change, journalise dans edit_history, et recalcule le
    statut. Retourne l'UE à jour + les champs encore manquants.
    """
    ue = (
        db.query(Ue)
        .filter(Ue.ue_uuid == ue_uuid, Ue.user_ref1 == user_ref1)
        .first()
    )
    if ue is None:
        raise HTTPException(status_code=404, detail="UE introuvable")

    try:
        validation = ue_edit_service.apply_patch(db, ue, body.fields, current_user)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )

    db.commit()
    db.refresh(ue)
    return UeEditResultOut(ue=ue, validation=validation)
