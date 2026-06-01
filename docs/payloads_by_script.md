# Payloads par script

Référence des champs de payload pour chaque script exposé via le dispatcher Flask (`POST /run`).

**Légende** : R = requis, O = optionnel, – = non utilisé  
**Règle** : les champs enrichis entre scripts (ex: `output_dir` résolu par `name_builder` et transmis à `download_kizeo_file`) sont marqués R dans le script qui les consomme, même s'ils ne viennent pas directement de Make.

> `user_ref1` ne doit **jamais** venir de la payload Make — il est toujours résolu depuis la BD via `user_id`.

---

## 1. Dictionnaire des champs

| Champ | Type | Description |
|---|---|---|
| `form_id` | string/int | ID du formulaire Kizeo |
| `data_id` | string/int | ID d'un enregistrement Kizeo |
| `user_id` | string/int | ID utilisateur Kizeo (résolu → `user_ref1` en BD) |
| `bd` | string | Nom de la base PostgreSQL cible (ex: `chlorofile2`) |
| `year_suffix` | string | Clé d'année (ex: `2025-2026`) |
| `ue` | string | Unité d'échantillonnage |
| `region` | string | Code région |
| `export_name` | string | Nom lisible de l'export Kizeo (ILIKE sur `app.kizeo_form_exports.name_excel`) |
| `export_type` | string | `excel` (défaut) ou `pdf` |
| `export_id` | string/int | ID Kizeo de l'export (résolu en BD, jamais fourni par Make) |
| `form_name` | string | Nom du formulaire (O: si absent, résolu depuis le catalogue) |
| `output_dir` | string | Chemin SharePoint relatif sous `General/` (sans `General\`) — résolu par `name_builder` ou `ddif_name_builder` |
| `output_path` | string | Chemin complet du fichier exporté (pour logging) |
| `run_dir` | string | Dossier contenant les JSON d'un run (`data/*.json`) |
| `db_schema` | string | Schéma PostgreSQL cible pour l'upsert (alias accepté: `schema`) |
| `upsert_mode` | string | `single` (défaut) ou `batch` — forcé `batch` si plusieurs JSON |
| `action` | string | Action Kizeo à traiter (ex: `import_pg`) |
| `dry_run` | bool | Si true, n'appelle pas l'API Kizeo (test uniquement) |
| `limit` | int | Limite d'IDs récupérés depuis la BD (usage test) |
| `load_pg` | bool | Si true (défaut), charge les données en PostgreSQL |
| `save_raw` | bool | Si true, dump le JSON brut sur disque |
| `only_sheets` | array[string] | Feuilles Excel à traiter (défaut: toutes ou liste standard) |
| `filename` | string | Nom de fichier de l'export (pour `register_kizeo_export`) |
| `size_bytes` | int | Taille du fichier exporté en octets |

---

## 2. Pipeline ingestion Kizeo → PostgreSQL

Flux : **Make** → `kizeo_schema_builder` (une fois) puis **Make** → `fetch_data_kizeo_api` → `upsert_data_postgresql` (automatique)

| Champ | `sync_kizeo_catalog` | `kizeo_schema_builder` | `fetch_data_kizeo_api` | `upsert_data_postgresql` |
|---|---|---|---|---|
| `form_id` | O | R | R | R |
| `data_id` | – | O | O | – |
| `user_id` | – | R | – | – |
| `bd` | R | R | R | R |
| `year_suffix` | – | R | – | – |
| `ue` | – | O | – | – |
| `region` | – | O | – | – |
| `export_name` | – | R | – | – |
| `export_type` | – | O | – | – |
| `form_name` | – | O | – | – |
| `run_dir` | – | – | R | R |
| `db_schema` | – | – | – | R |
| `upsert_mode` | – | O | O | O |
| `load_pg` | O | – | – | – |
| `save_raw` | O | – | – | – |

**Notes :**
- `sync_kizeo_catalog` sans `form_id` → mode global (toutes les forms et listes). Avec `form_id` → mode single (appelé automatiquement par `kizeo_schema_builder`).
- `kizeo_schema_builder` appelle `sync_kizeo_catalog` puis `fetch_data_kizeo_api` en interne.
- `fetch_data_kizeo_api` appelle `upsert_data_postgresql` en interne. Le `run_dir` est fourni par Make ou généré automatiquement.
- `upsert_data_postgresql` génère `ids_to_mark_read.txt` et appelle `mark_action_kizeo_api.py` (CLI) en subprocess.
- `db_schema` dans `upsert_data_postgresql` = `form_id` dans la quasi-totalité des cas (le schéma PostgreSQL porte le même nom que le formulaire).

---

## 3. Pipeline export Kizeo → SharePoint

Flux : **Make** → `name_builder` → `download_kizeo_file` → `register_kizeo_export` → `build_rapport_execution` (si ue+region présents)

| Champ | `name_builder` | `download_kizeo_file` | `register_kizeo_export` | `build_rapport_execution` |
|---|---|---|---|---|
| `form_id` | R | R | R | R |
| `data_id` | R | R | R | O |
| `user_id` | R | – | – | – |
| `bd` | R | R | R | R |
| `year_suffix` | R | – | O | R |
| `ue` | O | O | O | R |
| `region` | O | O | O | R |
| `export_name` | R | – | – | – |
| `export_type` | O | R | R | – |
| `export_id` | – | R | R | – |
| `form_name` | O | – | O | R |
| `output_dir` | – | R | R | R |
| `output_path` | – | – | R | – |
| `filename` | – | – | R | – |
| `size_bytes` | – | – | O | – |

**Notes :**
- **`name_builder`** est le point d'entrée Make. Il résout depuis la BD : `export_id`, `user_ref1`, `coop_code`, `form_name`, et construit `output_dir`. Il transmet la payload enrichie à `download_kizeo_file`.
- **`download_kizeo_file`** est rarement appelé directement par Make — il reçoit la payload enrichie de `name_builder`.
- **`register_kizeo_export`** peut recevoir un champ `action` ou `mode` pour basculer en mode suppression (`delete`) : supprime le fichier SharePoint + marque `deleted_at` dans les logs.
- **`build_rapport_execution`** est déclenché automatiquement par `register_kizeo_export` si `ue`, `region`, `output_dir`, `form_id`, `year_suffix` et `form_name` sont tous présents. Il n'est typiquement pas appelé directement par Make.
- `user_ref1` apparaît dans les payloads enrichies mais ne vient jamais de Make — il est résolu par `name_builder` via `user_id`.

---

## 4. Pipeline DDIF

Flux : **Make** → `ddif_name_builder` → `build_ddif_exports` (subprocess)

| Champ | `ddif_name_builder` |
|---|---|
| `form_id` | R |
| `data_id` | R |
| `user_id` | R |
| `bd` | R |
| `year_suffix` | R |
| `region` | R |
| `ue` | O |
| `form_name` | O |

**Notes :**
- `ddif_name_builder` résout `output_dir` depuis la BD (même logique que `name_builder`) puis appelle `build_ddif_exports.py` comme subprocess.
- `build_ddif_exports` lit les templates DBF et la config SQL depuis `scripts/ddif/<year_suffix>/<form_name>/<region>/`.
- Le `form_name` est conservé **exactement** tel que retourné par la BD (pas de sanitization) car il sert de nom de dossier pour le pack DDIF.

---

## 5. Pipeline data manuelle → PostgreSQL

Flux : **Make** → `upsert_data_manuelle_db`

| Champ | `upsert_data_manuelle_db` |
|---|---|
| `bd` | R |
| `year_suffix` | R |
| `only_sheets` | O |

**Notes :**
- `only_sheets` est une liste de noms de feuilles à traiter. Défaut : `["prescription", "parcelle", "secteur_intervention_reb"]`.
- Les fichiers source sont lus depuis SharePoint via `app.get_data_manuelle_files(year_suffix)`.
- Via le dispatcher Flask, le push DB est toujours activé (`push_db=True`).

---

## 6. Pipeline listes Kizeo (data manuelle → listes Kizeo)

Flux : **Make** → `create_kizeo_lists_excel` → `create_kizeo_lists_json` (subprocess) → `upload_lists_to_kizeo` (subprocess)

| Champ | `create_kizeo_lists_excel` |
|---|---|
| `bd` | R |
| `year_suffix` | R |
| `only_sheets` | O |

**Notes :**
- Seul `create_kizeo_lists_excel` est un dispatcher Flask. Les deux stages suivants (`create_kizeo_lists_json`, `upload_lists_to_kizeo`) sont des scripts CLI appelés automatiquement en subprocess.
- `create_kizeo_lists_json` lit les Excels par feuille, génère les JSONs Kizeo selon le mapping `liste_kizeo_lists.py` (registre statique `sheet_name → list_id`).
- `upload_lists_to_kizeo` pousse les JSONs vers l'API Kizeo via `PUT /lists/{list_id}`.

---

## 7. Gestion utilisateurs et catalogue

| Champ | `create_kizeo_user_structure` | `sync_kizeo_catalog` | `mark_action_kizeo_api_as_unread` |
|---|---|---|---|
| `bd` | R | R | R |
| `form_id` | – | O | R |
| `load_pg` | O | O | – |
| `save_raw` | – | O | – |
| `output_dir` | O | O | – |
| `action` | – | – | O |
| `limit` | – | – | O |
| `dry_run` | – | – | O |

**Notes :**
- `create_kizeo_user_structure` : `load_pg` défaut true. `output_dir` défaut depuis `OUTPUT_DIR_CREATE_KIZEO_USER_STRUCTURE` (env). Tables cibles configurées via `PG_SCHEMA_USER` / `PG_TABLE_USER` (env).
- `sync_kizeo_catalog` : sans `form_id` → sync global (toutes les forms + listes). Avec `form_id` → sync d'un seul formulaire.
- `mark_action_kizeo_api_as_unread` : `action` défaut `import_pg`. Récupère tous les `_id` depuis `<form_id>.<form_id>` et les remet en UNREAD côté Kizeo. `dry_run=true` ne fait aucun appel API.

---

## 8. Scripts CLI/subprocess uniquement (pas de handle Flask)

Ces scripts ne sont **pas** appelables via `/run`. Ils sont invoqués en subprocess ou en ligne de commande.

| Script | Appelé par | Paramètres CLI principaux |
|---|---|---|
| `mark_action_kizeo_api.py` | `upsert_data_postgresql.py` | `--form_id`, `--ids_file`, `--bd`, `--action` |
| `build_ddif_exports.py` | `ddif_name_builder.py` | `--payload <JSON>` |
| `create_kizeo_lists_json.py` | `create_kizeo_lists_excel.py` | `--excel-dir`, `--year-suffix` |
| `upload_lists_to_kizeo.py` | `create_kizeo_lists_json.py` | `--json-dir`, `--year-suffix` |

---

## 9. Scripts supprimés (références à ne plus utiliser)

| Ancien nom | Remplacé par |
|---|---|
| `kizeo_schema_builder_export.py` | `sync_kizeo_catalog.py` |
| `export_kizeo_file.py` | `download_kizeo_file.py` |
| `create_kizeo_lists_structure.py` | supprimé (fonctionnalité intégrée ailleurs) |
