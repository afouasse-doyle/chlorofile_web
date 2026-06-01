from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ImportBatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    batch_uuid: uuid.UUID
    user_ref1: str
    year_suffix: str
    dbf_type: str
    original_filename: str
    file_size_bytes: int | None
    row_count: int | None
    status: str
    error_message: str | None
    committed_at: datetime | None
    created_at: datetime


class DBFPreviewOut(BaseModel):
    """Réponse à POST /imports/upload — aperçu normalisé, rien n'est écrit en métier."""

    batch_uuid: uuid.UUID
    dbf_type: str
    original_filename: str
    total_rows: int

    raw_fields: list[str]                 # champs DBF bruts (MAJUSCULES)
    mapped_fields: dict[str, str]         # source_field → target_field reconnus
    unmapped_fields: list[str]            # présents dans le fichier, sans alias
    missing_targets: list[str]            # target_field attendus mais absents du fichier
    preview_rows: list[dict[str, Any]]    # N premières lignes normalisées
    ue_key_present: bool
    can_commit: bool                      # ue_key_present && total_rows > 0
