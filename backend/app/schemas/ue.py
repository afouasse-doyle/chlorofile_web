from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class UeOut(BaseModel):
    """Représentation d'une UE (liste et détail)."""
    model_config = ConfigDict(from_attributes=True)

    ue_uuid: uuid.UUID
    user_ref1: str
    year_suffix: str
    unite_d_echantillonnage_ue: str

    # Auto (DBF)
    code_dica: str | None
    no_prescription: str | None
    secteur_intervention: str | None
    chantier: str | None
    uaf: str | None
    code_ratf: str | None
    contrat: str | None
    projet: str | None
    ha_prescription: Decimal | None
    entrepreneur_travaux: str | None
    debut: date | None
    fin: date | None

    # Dérivé
    traitement: str | None

    # Manuel (extrait — saisie web)
    region: str | None
    gradient_intensite: str | None
    rayon: Decimal | None
    plant_ha: Decimal | None
    traitement_ps: str | None
    denombrement_cn: int | None
    taux_occ_andain: Decimal | None

    # Métadonnées
    statut_validation: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
