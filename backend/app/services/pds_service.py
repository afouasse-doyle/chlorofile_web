"""
Écriture en base des parcelles à partir d'un lot d'import (fichier de type PDS).

Au commit, on lit les lignes stagées (import_batch_rows.normalized_data), et pour
chaque ligne on :
  - récupère la UE liée via unite_d_echantillonnage_ue (doit exister dans appweb.ue)
  - upsert dans appweb.parcelles sur (ue_id, numero_de_parcelle)
  - désactive (is_active=False) les parcelles absentes du lot pour les UE concernées

Si une UE référencée n'existe pas en base, la ligne est ignorée (warning) — les
autres parcelles sont écrites. Le retour inclut parcelle_skipped pour traçabilité.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from app.models.import_batch import ImportBatch, ImportBatchRow
from app.models.parcelle import Parcelle
from app.models.ue import Ue
from app.services import validation_service

logger = logging.getLogger(__name__)


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


def commit_batch(db: Session, batch: ImportBatch) -> dict[str, int]:
    """
    Écrit les parcelles d'un lot PDS en base.

    Règle métier : une parcelle ne s'accroche qu'à une UE existante ET `valide`
    (tous les obligatoires remplis). Une UE incomplète est ignorée sans que ses
    parcelles existantes soient touchées.

    Compteurs retournés :
      parcelle_created, parcelle_updated, parcelle_deactivated, ue_touched,
      parcelle_skipped_invalide      (ligne sans NO_UE ou NO_PLACET),
      parcelle_skipped_ue_absente    (UE inexistante en base),
      parcelle_skipped_ue_incomplete (UE existe mais non valide).
    """
    rows = (
        db.query(ImportBatchRow)
        .filter(ImportBatchRow.batch_id == batch.id)
        .order_by(ImportBatchRow.row_index)
        .all()
    )

    # Cache UE : {ue_code → Ue | None} pour éviter N requêtes DB
    ue_cache: dict[str, Ue | None] = {}
    # Cache de validité : {ue_id → is_valid} — un seul passage du juge par UE
    valid_cache: dict[int, bool] = {}

    # (ue_id, numero_de_parcelle) traités dans ce lot
    seen: set[tuple[int, str]] = set()
    # UE ids touchées — sert à désactiver les parcelles absentes
    touched_ue_ids: set[int] = set()

    created = updated = 0
    skipped_invalide = skipped_ue_absente = skipped_ue_incomplete = 0

    for row in rows:
        nd = row.normalized_data or {}
        ue_code = nd.get("unite_d_echantillonnage_ue")
        numero = nd.get("numero_de_parcelle")

        if not ue_code:
            logger.warning(
                "Ligne %d ignorée : unite_d_echantillonnage_ue absent",
                row.row_index,
            )
            skipped_invalide += 1
            continue

        if not numero:
            logger.warning(
                "Ligne %d ignorée : numero_de_parcelle absent (UE=%s)",
                row.row_index,
                ue_code,
            )
            skipped_invalide += 1
            continue

        ue_code = str(ue_code).strip()
        numero = str(numero).strip()

        # Résolution UE avec cache
        if ue_code not in ue_cache:
            ue_cache[ue_code] = (
                db.query(Ue)
                .filter(
                    Ue.user_ref1 == batch.user_ref1,
                    Ue.year_suffix == batch.year_suffix,
                    Ue.unite_d_echantillonnage_ue == ue_code,
                )
                .first()
            )

        ue = ue_cache[ue_code]
        if ue is None:
            logger.warning(
                "Ligne %d ignorée : UE '%s' introuvable (user_ref1=%s year_suffix=%s)",
                row.row_index,
                ue_code,
                batch.user_ref1,
                batch.year_suffix,
            )
            skipped_ue_absente += 1
            continue

        # Gate « UE valide » — le juge tranche la complétude (caché par UE)
        if ue.id not in valid_cache:
            valid_cache[ue.id] = validation_service.validate_ue(db, ue).is_valid
        if not valid_cache[ue.id]:
            logger.warning(
                "Ligne %d ignorée : UE '%s' incomplète (non valide)",
                row.row_index,
                ue_code,
            )
            skipped_ue_incomplete += 1
            continue

        touched_ue_ids.add(ue.id)
        seen.add((ue.id, numero))

        parcel_data = {
            "type_placette": nd.get("type_placette"),
            "methode_production": nd.get("methode_production"),
            "production_source": nd.get("production_source"),
            "date_production_source": _to_date(nd.get("date_production_source")),
            "plant_ha": _to_decimal(nd.get("plant_ha")),
            "garmin": nd.get("garmin"),
            "secteur_intervention": nd.get("secteur_intervention"),
        }

        existing = (
            db.query(Parcelle)
            .filter(
                Parcelle.ue_id == ue.id,
                Parcelle.numero_de_parcelle == numero,
            )
            .first()
        )

        if existing is None:
            db.add(
                Parcelle(
                    ue_id=ue.id,
                    user_ref1=batch.user_ref1,
                    numero_de_parcelle=numero,
                    source_batch_id=batch.id,
                    is_active=True,
                    **parcel_data,
                )
            )
            created += 1
        else:
            for k, v in parcel_data.items():
                setattr(existing, k, v)
            existing.source_batch_id = batch.id
            existing.is_active = True
            updated += 1

    db.flush()

    # Désactiver les parcelles absentes du lot, seulement pour les UE touchées
    deactivated = 0
    for ue_id in touched_ue_ids:
        active_parcelles = (
            db.query(Parcelle)
            .filter(
                Parcelle.ue_id == ue_id,
                Parcelle.is_active.is_(True),
            )
            .all()
        )
        for p in active_parcelles:
            if (ue_id, p.numero_de_parcelle) not in seen:
                p.is_active = False
                deactivated += 1

    db.flush()

    logger.info(
        "Écriture PDS batch=%s created=%d updated=%d deactivated=%d "
        "skip(invalide=%d absente=%d incomplete=%d) ue_touched=%d",
        batch.batch_uuid,
        created,
        updated,
        deactivated,
        skipped_invalide,
        skipped_ue_absente,
        skipped_ue_incomplete,
        len(touched_ue_ids),
    )
    return {
        "parcelle_created": created,
        "parcelle_updated": updated,
        "parcelle_deactivated": deactivated,
        "parcelle_skipped_invalide": skipped_invalide,
        "parcelle_skipped_ue_absente": skipped_ue_absente,
        "parcelle_skipped_ue_incomplete": skipped_ue_incomplete,
        "ue_touched": len(touched_ue_ids),
    }
