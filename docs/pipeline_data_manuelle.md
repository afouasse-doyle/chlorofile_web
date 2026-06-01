# Pipeline données manuelles

Ce document décrit les deux pipelines qui consomment les fichiers "données manuelles" stockés sur SharePoint :

1. **Data manuelle → PostgreSQL** : importe les données dans les tables de référence
2. **Data manuelle → Listes Kizeo** : génère et pousse les listes Kizeo depuis les mêmes fichiers

Les deux pipelines partagent la même source (fichiers SharePoint indexés en BD) mais sont déclenchés indépendamment par Make.

---

## Source commune : fichiers data manuelle

Les fichiers source sont des classeurs Excel multi-feuilles déposés sur SharePoint par les coopératives. Leurs chemins sont indexés dans PostgreSQL et retournés par :

```sql
SELECT file_path FROM app.get_data_manuelle_files(<year_suffix>)
```

Les chemins sont des chemins SharePoint relatifs (sous `General/`). Voir [sharepoint_structure.md](sharepoint_structure.md) pour le contexte de stockage.

---

## Pipeline 1 — Data manuelle → PostgreSQL

**Flux** : Make → `upsert_data_manuelle_db.py`

```
app.get_data_manuelle_files(year_suffix)
 │  Liste les fichiers actifs pour l'année
 ▼
sp_download_file() [graph_storage]
 │  Télécharge chaque classeur en local temporaire
 ▼
upsert_data_manuelle_db.py
 │  Fusionne les feuilles de tous les classeurs
 │  Génère un Excel preview (local temporaire)
 ├──► app.prescriptions         (feuille prescription)
 ├──► app.parcelles             (feuille parcelle)
 └──► app.secteur_intervention_reb  (feuille secteur_intervention_reb)
```

### Payload Make

| Champ | Requis | Description |
|---|---|---|
| `bd` | R | Base PostgreSQL cible |
| `year_suffix` | R | Clé d'année (ex: `2025-2026`) |
| `only_sheets` | O | Feuilles à traiter (défaut: `["prescription", "parcelle", "secteur_intervention_reb"]`) |

### Notes

- Via le dispatcher Flask, le push DB est toujours activé (`push_db=True`).
- Chaque feuille est mergée à travers tous les classeurs avant l'upsert.
- Les fichiers temporaires locaux sont nettoyés après usage — aucun stockage permanent en local.

---

## Pipeline 2 — Data manuelle → Listes Kizeo

**Flux** : Make → `create_kizeo_lists_excel.py` → `create_kizeo_lists_json.py` (subprocess) → `upload_lists_to_kizeo.py` (subprocess)

```
app.get_data_manuelle_files(year_suffix)
 │  Mêmes fichiers source que le pipeline 1
 ▼
create_kizeo_lists_excel.py  [Flask dispatcher]
 │  Télécharge les classeurs depuis SharePoint
 │  Fusionne les feuilles, écrit un Excel par feuille
 │  → scripts/listes/excel/<sheet>.xlsx
 ▼
create_kizeo_lists_json.py  [subprocess]
 │  Lit les Excel par feuille
 │  Résout le list_id via liste_kizeo_lists.py (registre statique sheet → list_id)
 │  Génère les JSON Kizeo avec sémantique de colonnes :
 │    user_ref1          → [[user_ref1=valeur]]
 │    level_label*       → hiérarchie avec \
 │    ref*               → val:val
 │  → scripts/listes/json/<sheet>.json
 ▼
upload_lists_to_kizeo.py  [subprocess]
 │  PUT /rest/v3/lists/{list_id}
 │  Remplace entièrement la liste Kizeo
 └──► Kizeo API
```

### Payload Make (`create_kizeo_lists_excel`)

| Champ | Requis | Description |
|---|---|---|
| `bd` | R | Base PostgreSQL (pour lire les fichiers source) |
| `year_suffix` | R | Clé d'année |
| `only_sheets` | O | Feuilles à traiter (défaut: toutes les feuilles connues) |

### Notes

- Seul `create_kizeo_lists_excel.py` est un dispatcher Flask — les deux autres stages sont appelés automatiquement en subprocess.
- `liste_kizeo_lists.py` est le registre statique `(sheet_name, year_suffix) → list_id`. Matching insensible à la casse et aux accents.
- L'upload Kizeo est un remplacement complet de la liste (`PUT`) — pas d'upsert partiel.
- `upload_lists_to_kizeo.py` utilise un verrou fichier pour éviter les exécutions simultanées.

---

## Scripts impliqués

| Script | Rôle | Type |
|---|---|---|
| `upsert_data_manuelle_db.py` | Import data manuelle → PostgreSQL | Flask dispatcher |
| `create_kizeo_lists_excel.py` | Fusion Excel + lancement pipeline listes | Flask dispatcher |
| `create_kizeo_lists_json.py` | Excel → JSON Kizeo | CLI / subprocess |
| `upload_lists_to_kizeo.py` | Upload JSON → API Kizeo | CLI / subprocess |
| `liste_kizeo_lists.py` | Registre statique sheet → list_id | Module utilitaire |

---

## Voir aussi

- [sharepoint_structure.md](sharepoint_structure.md) — hiérarchie des dossiers SharePoint (fichiers source)
- [payloads_by_script.md](payloads_by_script.md) — référence complète des champs de payload
- [scripts_overview.md](scripts_overview.md) — description de chaque script
- [pipeline_kizeo.md](pipeline_kizeo.md) — ingestion des formulaires Kizeo
- [pipeline_exports.md](pipeline_exports.md) — exports Excel/PDF
