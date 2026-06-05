"""
Édition manuelle d'une UE (PATCH).

Pilotée par field_definitions (pack-driven) : seuls les champs `is_editable`
peuvent être modifiés, chacun coercé selon son `data_type` et borné par
min_value/max_value. Chaque changement réel est journalisé dans edit_history.

Si `code_dica` change, `traitement` est re-dérivé (dica_codes) — indispensable
car les règles conditionnelles du juge en dépendent.

Après application, le statut est recalculé via le juge :
  - complet            → 'valide'
  - incomplet + édité  → 'en_cours'
La fonction lève ValueError sur toute entrée invalide ; le routeur la traduit en 422.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from app.models.dica_code import DicaCode
from app.models.edit_history import EditHistory
from app.models.field_definition import FieldDefinition
from app.models.ue import Ue
from app.models.user import User
from app.services import validation_service
from app.services.validation_service import UeValidation

logger = logging.getLogger(__name__)


def _editable_index(db: Session, ue: Ue) -> dict[str, FieldDefinition]:
    """Catalogue des champs UE pour l'année (l'année précise gagne sur '*')."""
    raw = (
        db.query(FieldDefinition)
        .filter(
            FieldDefinition.entity == "ue",
            FieldDefinition.year_suffix.in_([ue.year_suffix, "*"]),
            FieldDefinition.is_active.is_(True),
        )
        .all()
    )
    index: dict[str, FieldDefinition] = {}
    for fd in raw:
        existing = index.get(fd.field_name)
        if existing is None or (existing.year_suffix == "*" and fd.year_suffix != "*"):
            index[fd.field_name] = fd
    return index


def _coerce(fd: FieldDefinition, value: Any) -> Any:
    """Convertit la valeur entrante selon data_type. None si vide."""
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None

    dt = fd.data_type
    try:
        if dt in ("texte", "liste"):
            return str(value).strip()
        if dt == "entier":
            return int(value)
        if dt == "decimal":
            return Decimal(str(value))
        if dt == "date":
            if isinstance(value, date) and not isinstance(value, datetime):
                return value
            if isinstance(value, datetime):
                return value.date()
            return datetime.fromisoformat(str(value)[:10]).date()
        if dt == "booleen":
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in ("true", "1", "oui", "yes")
    except (ValueError, InvalidOperation):
        raise ValueError(f"Valeur invalide pour « {fd.label} » (type attendu : {dt})")

    return value


def _check_bounds(fd: FieldDefinition, value: Any) -> None:
    """Vérifie min/max pour les champs numériques."""
    if value is None or fd.data_type not in ("entier", "decimal"):
        return
    num = Decimal(str(value))
    if fd.min_value is not None and num < fd.min_value:
        raise ValueError(f"« {fd.label} » doit être ≥ {fd.min_value}")
    if fd.max_value is not None and num > fd.max_value:
        raise ValueError(f"« {fd.label} » doit être ≤ {fd.max_value}")


def _as_str(v: Any) -> str | None:
    return None if v is None else str(v)


def apply_patch(
    db: Session,
    ue: Ue,
    changes: dict[str, Any],
    user: User,
) -> UeValidation:
    """
    Applique les modifications sur une UE en session. Ne commit pas (le routeur
    commit). Retourne le verdict de validation recalculé.
    """
    if not changes:
        raise ValueError("Aucun champ à modifier")

    index = _editable_index(db, ue)

    # 1. Valider + coercer toutes les valeurs AVANT d'écrire quoi que ce soit
    coerced: dict[str, Any] = {}
    for field_name, raw_value in changes.items():
        fd = index.get(field_name)
        if fd is None:
            raise ValueError(f"Champ inconnu : {field_name}")
        if not fd.is_editable:
            raise ValueError(f"Champ non éditable : {field_name}")
        value = _coerce(fd, raw_value)
        _check_bounds(fd, value)
        coerced[field_name] = value

    # 2. Appliquer en détectant les changements réels (pour l'historique)
    changed: list[tuple[str, Any, Any]] = []
    for field_name, new_value in coerced.items():
        old_value = getattr(ue, field_name, None)
        if old_value != new_value:
            setattr(ue, field_name, new_value)
            changed.append((field_name, old_value, new_value))

    # 3. Re-dériver traitement si code_dica a changé
    if "code_dica" in coerced and any(c[0] == "code_dica" for c in changed):
        old_trait = ue.traitement
        dica = db.query(DicaCode).filter(DicaCode.code_dica == ue.code_dica).first()
        new_trait = dica.traitement if dica else None
        if old_trait != new_trait:
            ue.traitement = new_trait
            changed.append(("traitement", old_trait, new_trait))

    # 4. Journaliser chaque changement
    for field_name, old_value, new_value in changed:
        db.add(
            EditHistory(
                user_ref1=ue.user_ref1,
                entity_type="ue",
                entity_id=ue.id,
                field_name=field_name,
                old_value=_as_str(old_value),
                new_value=_as_str(new_value),
                changed_by=user.email,
            )
        )

    # 5. Recalculer la complétude (lit les valeurs déjà appliquées en session)
    result = validation_service.validate_ue(db, ue)

    # 6. Statut : valide si complet, sinon en_cours dès qu'une modif a eu lieu
    if result.is_valid:
        ue.statut_validation = "valide"
    elif changed:
        ue.statut_validation = "en_cours"

    db.flush()
    logger.info(
        "UE éditée ue_uuid=%s par=%s champs_modifiés=%d statut=%s",
        ue.ue_uuid, user.email, len(changed), ue.statut_validation,
    )
    return result
