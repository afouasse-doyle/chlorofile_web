"""
Router : consultation des UE.

GET /ue            → liste des UE de la coop de l'utilisateur connecté
GET /ue/{ue_uuid}  → détail d'une UE

Toujours scopé par user_ref1 (du token) — cloisonnement par coop.
"""

import uuid as uuid_lib

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_active_user_ref1
from app.models.ue import Ue
from app.schemas.ue import UeOut

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
