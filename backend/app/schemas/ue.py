from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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


class MissingFieldOut(BaseModel):
    """Un champ obligatoire manquant retourné par le juge de validation."""
    model_config = ConfigDict(from_attributes=True)

    field_name: str
    label: str
    requirement: str          # 'R' ou 'C'
    message: str | None = None


class UeValidationOut(BaseModel):
    """Verdict de complétude d'une UE (champs manquants + statut calculé)."""
    model_config = ConfigDict(from_attributes=True)

    ue_uuid: uuid.UUID
    statut: str               # 'valide' | 'non_valide' (complétude pure)
    is_valid: bool
    missing: list[MissingFieldOut]


class UePatchIn(BaseModel):
    """Corps d'édition : { field_name: valeur, ... } pour les champs éditables."""
    model_config = ConfigDict(extra="forbid")

    fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Champs à modifier (clé = nom canonique, ex. 'region', 'rayon').",
    )


class UeEditResultOut(BaseModel):
    """Réponse du PATCH : l'UE à jour + le verdict de validation recalculé."""
    model_config = ConfigDict(from_attributes=True)

    ue: UeOut
    validation: UeValidationOut
