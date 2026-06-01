"""
Écriture en base des UE à partir d'un lot d'import (fichier de type UE).

Au commit, on lit les lignes stagées (import_batch_rows.normalized_data), on les
regroupe par unite_d_echantillonnage_ue, et pour chaque UE on :
  - SOMME ha_prescription sur toutes les lignes de la UE
  - prend la première valeur non-nulle des champs UE-niveau (auto, du DBF)
  - DÉRIVE traitement depuis code_dica (table dica_codes)
  - upsert dans appweb.ue sur (user_ref1, year_suffix, unite_d_echantillonnage_ue)

Les champs manuels (region, gradient_intensite, rayon…) restent nuls à l'import :
ils seront complétés dans le formulaire web.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from app.models.dica_code import DicaCode
from app.models.import_batch import ImportBatch, ImportBatchRow
from app.models.ue import Ue

logger = logging.getLogger(__name__)

# Champs UE-niveau pris tels quels du DBF (première valeur non-nulle de la UE)
_UE_FIRST_FIELDS = [
    "code_dica", "no_prescription", "secteur_intervention", "chantier",
    "uaf", "code_ratf", "contrat", "projet", "entrepreneur_travaux", "region",
]
_DATE_FIELDS = ["debut", "fin"]


def _to_decimal(v: Any) -> Decimal | None:
    if v in (None, ""):
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def _to_date(v: Any) -> date | None:
    if not v:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v)
    try:
        return datetime.fromisoformat(s).date()
    except ValueError:
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").date()
        except ValueError:
            return None


def _first(values: list[Any]) -> Any:
    for v in values:
        if v not in (None, ""):
            return v
    return None


def commit_batch(db: Session, batch: ImportBatch) -> dict[str, int]:
    """Éclate les lignes stagées du lot vers appweb.ue. Retourne les compteurs."""
    rows = (
        db.query(ImportBatchRow)
        .filter(ImportBatchRow.batch_id == batch.id)
        .order_by(ImportBatchRow.row_index)
        .all()
    )

    # Table de dérivation code_dica → traitement
    dica = {d.code_dica: d.traitement for d in db.query(DicaCode).all()}

    # Regrouper les lignes normalisées par UE
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        nd = r.normalized_data or {}
        ue_code = nd.get("unite_d_echantillonnage_ue")
        if ue_code:
            groups[str(ue_code).strip()].append(nd)

    created = updated = 0
    for ue_code, recs in groups.items():
        # Somme des hectares de la UE
        ha = sum((_to_decimal(rec.get("ha_prescription")) or Decimal(0)) for rec in recs)
        ha = ha if ha != 0 else None

        # Champs UE-niveau (première valeur non-nulle)
        data = {f: _first([rec.get(f) for rec in recs]) for f in _UE_FIRST_FIELDS}
        for f in _DATE_FIELDS:
            data[f] = _to_date(_first([rec.get(f) for rec in recs]))

        # Dérivation du traitement
        traitement = dica.get(data.get("code_dica")) if data.get("code_dica") else None

        existing = (
            db.query(Ue)
            .filter(
                Ue.user_ref1 == batch.user_ref1,
                Ue.year_suffix == batch.year_suffix,
                Ue.unite_d_echantillonnage_ue == ue_code,
            )
            .first()
        )

        if existing is None:
            db.add(Ue(
                user_ref1=batch.user_ref1,
                year_suffix=batch.year_suffix,
                unite_d_echantillonnage_ue=ue_code,
                ha_prescription=ha,
                traitement=traitement,
                source_batch_id=batch.id,
                is_active=True,
                **data,
            ))
            created += 1
        else:
            for k, v in data.items():
                setattr(existing, k, v)
            existing.ha_prescription = ha
            existing.traitement = traitement
            existing.source_batch_id = batch.id
            existing.is_active = True
            updated += 1

    db.flush()
    logger.info(
        "Écriture UE batch=%s ue_created=%d ue_updated=%d",
        batch.batch_uuid, created, updated,
    )
    return {"ue_created": created, "ue_updated": updated, "ue_total": len(groups)}
