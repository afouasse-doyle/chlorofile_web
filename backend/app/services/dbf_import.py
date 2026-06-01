"""
Service d'import DBF — étape preview uniquement.

Responsabilité : lire un fichier DBF, appliquer le mapping appweb.dbf_field_aliases
(résolution par priority), et produire un aperçu normalisé. Aucune écriture métier
à cette étape — on ne fait que lire le fichier et la table d'alias.

Flux :
    fichier DBF brut
        → lecture des champs présents (MAJUSCULES)
        → chargement des alias actifs (appweb.dbf_field_aliases)
        → pour chaque ligne : résolution priority par target_field
        → DBFPreview (champs reconnus / inconnus / attendus-absents, aperçu N lignes)

La résolution priority : un même target_field peut avoir plusieurs sources
(ex: NO_UAF priority 10, NO_UA priority 20 → uaf). Quand plusieurs sources sont
présentes dans la ligne, la plus basse priority avec une valeur non-nulle gagne.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dbfread import DBF
from sqlalchemy.orm import Session

from app.models.field_alias import DbfFieldAlias

logger = logging.getLogger(__name__)

# Nombre de lignes renvoyées dans l'aperçu (les lignes complètes sont stagées au commit)
PREVIEW_ROWS = 10


@dataclass
class DBFPreview:
    """Résultat de l'étape preview — aucune donnée métier écrite."""

    dbf_type: str
    original_filename: str
    total_rows: int

    # Champs DBF bruts détectés dans le fichier (MAJUSCULES)
    raw_fields: list[str]

    # Champs reconnus : {source_field → target_field} effectivement utilisés
    mapped_fields: dict[str, str]

    # Champs présents dans le fichier mais sans alias actif
    unmapped_fields: list[str]

    # target_field attendus (alias actif) dont aucune source n'est présente dans le fichier
    missing_targets: list[str]

    # Aperçu des N premières lignes normalisées (clés = target_field)
    preview_rows: list[dict[str, Any]]

    # Toutes les lignes (brutes + normalisées) — utilisées pour le staging au commit
    all_rows_raw: list[dict[str, Any]]
    all_rows_normalized: list[dict[str, Any]]

    # unite_d_echantillonnage_ue doit être présent pour qu'un commit soit possible
    ue_key_present: bool = False


def load_alias_resolver(db: Session) -> dict[str, list[tuple[int, str]]]:
    """
    Construit le résolveur d'alias : {target_field → [(priority, SOURCE_FIELD_UPPER), ...]}
    trié par priority croissante. Les alias DBF s'appliquent à tous les types
    (source_type='dbf') — le type de DBF est porté par le lot, pas par l'alias.
    """
    rows = (
        db.query(DbfFieldAlias)
        .filter(DbfFieldAlias.is_active.is_(True))
        .filter(DbfFieldAlias.source_type == "dbf")
        .all()
    )
    resolver: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for r in rows:
        resolver[r.target_field].append((r.priority, r.source_field.upper()))
    for target in resolver:
        resolver[target].sort(key=lambda t: t[0])  # priority croissante
    return dict(resolver)


def _normalize_value(value: Any) -> Any:
    """Strip des chaînes, None pour les vides."""
    if isinstance(value, str):
        v = value.strip()
        return v if v else None
    return value


def _normalize_row(
    raw_row_upper: dict[str, Any],
    resolver: dict[str, list[tuple[int, str]]],
) -> dict[str, Any]:
    """
    Applique le résolveur priority sur une ligne brute (clés MAJUSCULES).
    Pour chaque target_field, prend la première source (par priority) présente
    avec une valeur non-nulle.
    """
    normalized: dict[str, Any] = {}
    for target_field, sources in resolver.items():
        for _priority, source_field in sources:
            if source_field in raw_row_upper:
                value = _normalize_value(raw_row_upper[source_field])
                if value is not None:
                    normalized[target_field] = value
                    break
    return normalized


def preview(
    db: Session,
    dbf_path: Path,
    dbf_type: str,
    original_filename: str,
) -> DBFPreview:
    """
    Lit le fichier DBF, applique les alias et retourne un aperçu normalisé
    + toutes les lignes (brutes et normalisées) prêtes à être stagées.
    N'écrit rien en base.

    Args:
        db: Session SQLAlchemy (lecture seule — charge appweb.dbf_field_aliases)
        dbf_path: chemin local du .dbf temporaire
        dbf_type: 'PLR', 'RXF' ou 'PDS' (porté par le lot, sert au routage commit)
        original_filename: nom original (affichage)
    """
    dbf_type = dbf_type.upper()
    resolver = load_alias_resolver(db)

    # Ensemble des SOURCE_FIELD connus (tous targets confondus) pour le diagnostic
    known_sources = {src for sources in resolver.values() for _p, src in sources}

    try:
        table = DBF(str(dbf_path), lowernames=False, ignore_missing_memofile=True)
        raw_fields = [f.name.upper() for f in table.fields]
    except Exception as exc:
        logger.error("Erreur lecture DBF %s : %s", dbf_path, exc)
        raise ValueError(f"Impossible de lire le fichier DBF : {exc}") from exc

    raw_fields_set = set(raw_fields)

    # Lecture + normalisation de toutes les lignes
    all_rows_raw: list[dict[str, Any]] = []
    all_rows_normalized: list[dict[str, Any]] = []
    for raw_row in table:
        raw_upper = {str(k).upper(): v for k, v in dict(raw_row).items()}
        all_rows_raw.append(raw_upper)
        all_rows_normalized.append(_normalize_row(raw_upper, resolver))

    total_rows = len(all_rows_raw)

    # Diagnostic des champs
    # mapped_fields : source → target effectivement présents dans le fichier
    mapped_fields: dict[str, str] = {}
    for target_field, sources in resolver.items():
        for _priority, source_field in sources:
            if source_field in raw_fields_set:
                mapped_fields[source_field] = target_field

    unmapped_fields = sorted(f for f in raw_fields if f not in known_sources)

    # target_field dont AUCUNE source n'est présente dans le fichier
    missing_targets = sorted(
        target
        for target, sources in resolver.items()
        if not any(src in raw_fields_set for _p, src in sources)
    )

    preview_rows = all_rows_normalized[:PREVIEW_ROWS]
    ue_key_present = any(
        "unite_d_echantillonnage_ue" in row for row in all_rows_normalized
    )

    logger.info(
        "DBF preview ok type=%s file=%s rows=%d mapped=%d unmapped=%d missing_targets=%d",
        dbf_type,
        original_filename,
        total_rows,
        len(mapped_fields),
        len(unmapped_fields),
        len(missing_targets),
    )

    return DBFPreview(
        dbf_type=dbf_type,
        original_filename=original_filename,
        total_rows=total_rows,
        raw_fields=raw_fields,
        mapped_fields=mapped_fields,
        unmapped_fields=unmapped_fields,
        missing_targets=missing_targets,
        preview_rows=preview_rows,
        all_rows_raw=all_rows_raw,
        all_rows_normalized=all_rows_normalized,
        ue_key_present=ue_key_present,
    )
