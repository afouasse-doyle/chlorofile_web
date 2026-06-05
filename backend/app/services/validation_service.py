"""
Le « juge » de validation d'une UE.

Une seule source de vérité pour « cette UE est-elle complète ? », réutilisée par :
  1. l'édition web (PATCH) → met à jour statut_validation au fil de la saisie
  2. le gate PDS → refuse les parcelles si l'UE n'est pas valide
  3. le gate Kizeo → ne pousse que les UE valides

Contrat (validé avec le métier) :
  - field_definitions porte le requirement : 'R' (requis), 'O' (optionnel), 'C' (conditionnel)
  - 'R' → toujours requis
  - 'C' → requis SEULEMENT si la règle nommée (validation_rules.rule_name) matche cette UE
          sur (year_suffix, region, traitement) selon traitement_match (exact|in|contains)
  - 'O' → ne bloque jamais
  - « requis » = présence (non-null / non-vide). L'appartenance d'un champ liste à sa
    liste est garantie par le frontend (dropdown) — pas vérifiée ici.

La fonction est PURE : elle calcule et retourne le verdict, elle n'écrit rien.
Le caller décide de persister statut_validation (ex : le PATCH).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.field_definition import FieldDefinition
from app.models.ue import Ue
from app.models.validation_rule import ValidationRule

logger = logging.getLogger(__name__)


@dataclass
class MissingField:
    field_name: str
    label: str
    requirement: str          # 'R' ou 'C'
    message: str | None = None


@dataclass
class UeValidation:
    ue_uuid: str
    statut: str               # 'valide' | 'non_valide' (complétude pure)
    is_valid: bool
    missing: list[MissingField]


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _rule_matches(rule: ValidationRule, ue: Ue) -> bool:
    """La règle conditionnelle s'applique-t-elle à cette UE ?"""
    if rule.year_suffix not in ("*", ue.year_suffix):
        return False
    if rule.region != "*" and (rule.region or "") != (ue.region or ""):
        return False

    target = rule.traitement or "*"
    if target == "*":
        return True

    ue_trait = ue.traitement or ""
    match = rule.traitement_match
    if match == "exact":
        return ue_trait == target
    if match == "in":
        return ue_trait in [t.strip() for t in target.split(",")]
    if match == "contains":
        return target in ue_trait
    return False


def validate_ue(db: Session, ue: Ue) -> UeValidation:
    """Calcule la complétude d'une UE. Pure : n'écrit rien en base."""
    # Catalogue des champs pour cette année (l'année précise gagne sur '*')
    raw_defs = (
        db.query(FieldDefinition)
        .filter(
            FieldDefinition.entity == "ue",
            FieldDefinition.year_suffix.in_([ue.year_suffix, "*"]),
            FieldDefinition.is_active.is_(True),
        )
        .all()
    )
    by_name: dict[str, FieldDefinition] = {}
    for fd in raw_defs:
        existing = by_name.get(fd.field_name)
        if existing is None or (existing.year_suffix == "*" and fd.year_suffix != "*"):
            by_name[fd.field_name] = fd
    field_defs = list(by_name.values())

    # Règles conditionnelles actives, indexées par nom
    rules = {
        r.rule_name: r
        for r in db.query(ValidationRule).filter(ValidationRule.is_active.is_(True)).all()
        if r.rule_name
    }

    missing: list[MissingField] = []

    for fd in field_defs:
        value = getattr(ue, fd.field_name, None)

        required = False
        if fd.requirement == "R":
            required = True
        elif fd.requirement == "C" and fd.validation_rule:
            rule = rules.get(fd.validation_rule)
            if rule is not None and _rule_matches(rule, ue):
                required = True

        if required and _is_empty(value):
            rule = rules.get(fd.validation_rule) if fd.validation_rule else None
            missing.append(
                MissingField(
                    field_name=fd.field_name,
                    label=fd.label,
                    requirement=fd.requirement,
                    message=rule.message if rule else None,
                )
            )

    # Le juge ne tranche que la complétude. 'en_cours' (édition commencée) est posé
    # par le PATCH, pas déduit ici.
    return UeValidation(
        ue_uuid=str(ue.ue_uuid),
        statut="valide" if not missing else "non_valide",
        is_valid=not missing,
        missing=sorted(missing, key=lambda m: m.field_name),
    )
