"""
Router : imports DBF

POST /imports/upload         → lecture + normalisation + staging des lignes (preview)
POST /imports/{uuid}/commit  → éclatement des lignes stagées vers ue / parcelles
GET  /imports/               → liste des lots d'import
"""

import logging
import tempfile
import uuid as uuid_lib
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_active_user_ref1
from app.models.import_batch import ImportBatch, ImportBatchRow
from app.schemas.import_batch import DBFPreviewOut, ImportBatchOut
from app.services import dbf_import as dbf_service
from app.services import ue_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/imports", tags=["imports"])

# 2 types seulement : UE (prescription/unité d'échantillonnage) et PDS (parcelles).
# Les variations de champs entre régions sont absorbées par dbf_field_aliases.
ALLOWED_DBF_TYPES = {"UE", "PDS"}


@router.post("/upload", response_model=DBFPreviewOut, status_code=status.HTTP_200_OK)
async def upload_dbf(
    file: UploadFile = File(...),
    dbf_type: str = Form(...),
    year_suffix: str = Form(...),
    user_ref1: str = Depends(get_active_user_ref1),
    db: Session = Depends(get_db),
):
    """
    Reçoit un fichier DBF, produit un aperçu normalisé et stage toutes les lignes.
    Crée un ImportBatch (status='preview') + les ImportBatchRow associées.
    Aucune donnée métier (ue/parcelles) n'est écrite — ça reste au commit.

    user_ref1 vient du token (utilisateur connecté), jamais du formulaire — clé RLS.
    """
    dbf_type = dbf_type.upper()
    if dbf_type not in ALLOWED_DBF_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"dbf_type invalide. Valeurs acceptées : {sorted(ALLOWED_DBF_TYPES)}",
        )

    content = await file.read()
    file_size = len(content)

    with tempfile.NamedTemporaryFile(suffix=".dbf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        preview = dbf_service.preview(
            db=db,
            dbf_path=tmp_path,
            dbf_type=dbf_type,
            original_filename=file.filename or "inconnu.dbf",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    finally:
        tmp_path.unlink(missing_ok=True)

    # Persistance du lot + staging des lignes (raw + normalized)
    batch = ImportBatch(
        user_ref1=user_ref1,
        year_suffix=year_suffix,
        dbf_type=dbf_type,
        original_filename=file.filename or "inconnu.dbf",
        file_size_bytes=file_size,
        row_count=preview.total_rows,
        status="preview",
    )
    db.add(batch)
    db.flush()  # obtient batch.id sans commit final

    for idx, (raw, norm) in enumerate(
        zip(preview.all_rows_raw, preview.all_rows_normalized)
    ):
        db.add(
            ImportBatchRow(
                batch_id=batch.id,
                row_index=idx,
                raw_data=_jsonable(raw),
                normalized_data=_jsonable(norm),
            )
        )

    db.commit()
    db.refresh(batch)

    can_commit = preview.ue_key_present and preview.total_rows > 0

    return DBFPreviewOut(
        batch_uuid=batch.batch_uuid,
        dbf_type=preview.dbf_type,
        original_filename=preview.original_filename,
        total_rows=preview.total_rows,
        raw_fields=preview.raw_fields,
        mapped_fields=preview.mapped_fields,
        unmapped_fields=preview.unmapped_fields,
        missing_targets=preview.missing_targets,
        preview_rows=[_jsonable(r) for r in preview.preview_rows],
        ue_key_present=preview.ue_key_present,
        can_commit=can_commit,
    )


@router.post("/{batch_uuid}/commit")
def commit_import(
    batch_uuid: uuid_lib.UUID,
    user_ref1: str = Depends(get_active_user_ref1),
    db: Session = Depends(get_db),
):
    """
    Valide un lot en statut 'preview' et écrit les données en base.
    UE → upsert appweb.ue (somme ha, dérivation traitement). PDS → à venir.
    """
    batch = (
        db.query(ImportBatch)
        .filter(ImportBatch.batch_uuid == batch_uuid)
        .filter(ImportBatch.user_ref1 == user_ref1)  # cloisonnement par coop
        .first()
    )
    if not batch:
        raise HTTPException(status_code=404, detail="Lot d'import introuvable")
    if batch.status != "preview":
        raise HTTPException(
            status_code=409,
            detail=f"Le lot est en statut '{batch.status}', commit impossible",
        )

    if batch.dbf_type == "UE":
        result = ue_service.commit_batch(db, batch)
    elif batch.dbf_type == "PDS":
        raise HTTPException(status_code=501, detail="Import PDS (parcelles) pas encore implémenté")
    else:
        raise HTTPException(status_code=422, detail=f"dbf_type inconnu : {batch.dbf_type}")

    batch.status = "committed"
    batch.committed_at = datetime.now(timezone.utc)
    db.commit()

    logger.info(
        "Import committed batch=%s type=%s user=%s result=%s",
        batch_uuid, batch.dbf_type, batch.user_ref1, result,
    )
    return {"batch_uuid": str(batch_uuid), "status": "committed", **result}


@router.get("/", response_model=list[ImportBatchOut])
def list_imports(
    year_suffix: str | None = None,
    user_ref1: str = Depends(get_active_user_ref1),
    db: Session = Depends(get_db),
):
    """Liste les lots d'import de la coop de l'utilisateur connecté."""
    q = db.query(ImportBatch).filter(ImportBatch.user_ref1 == user_ref1)
    if year_suffix:
        q = q.filter(ImportBatch.year_suffix == year_suffix)
    return q.order_by(ImportBatch.id.desc()).limit(100).all()


def _jsonable(row: dict) -> dict:
    """Convertit les types DBF non sérialisables (date, Decimal) en str pour JSONB."""
    import datetime as _dt
    from decimal import Decimal

    out = {}
    for k, v in row.items():
        if isinstance(v, (_dt.date, _dt.datetime)):
            out[k] = v.isoformat()
        elif isinstance(v, Decimal):
            out[k] = float(v)
        elif isinstance(v, bytes):
            out[k] = v.decode("latin-1", errors="replace").strip()
        else:
            out[k] = v
    return out
