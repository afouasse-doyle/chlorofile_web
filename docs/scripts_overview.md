# Aperçu des scripts Python

Documentation synthétique de tous les scripts du pipeline Kizeo → Flask → PostgreSQL → SharePoint.

> Règle générale : tous les scripts appelés par le dispatcher Flask exposent :
> ```python
> def handle(payload: dict, logger) -> dict:
> ```
> La validation Pydantic se fait **dans** `handle()` — jamais dans `run_flask_server.py`.
> Tout le SQL passe par `safe_db.py` — jamais d'SQL inline dans les scripts métier.
> Tout le stockage fichier passe par `graph_storage.py` (SharePoint / Graph) — aucun fichier local permanent.

---

## Organisation par rôle

| Rôle | Scripts |
|---|---|
| Dispatcher Flask | `handle(payload, logger) -> dict` |
| CLI uniquement | appelés directement ou via subprocess |
| Module utilitaire | importé, pas de `handle()` |
| Worker standalone | process autonome, boucle infinie |
| Infra / planifié | tâche Windows planifiée |
| Debug / test | usage manuel uniquement |

---

## Modules utilitaires fondamentaux

Ces modules sont importés par les autres scripts. Ils n'ont pas de `handle()`.

### `safe_db.py`
Source de vérité pour tout accès PostgreSQL. Aucun SQL n'est autorisé ailleurs.

- **`pg_connect(dbname)`** — charge `.env` une fois, retourne une connexion psycopg2
- **`exec_sql(conn, query, params, fetch, query_name)`** — exécute une requête paramétrée avec logging
- **Helpers métier** : `fetch_export_id`, `fetch_user_ref1`, `fetch_directory_from_coop`, `fetch_form_name_for_form_id`
- **Gestion utilisateurs Kizeo** : `ensure_kizeo_users_table_fixed`, `upsert_kizeo_users_rows_fixed`, `soft_delete_kizeo_users_not_in`, `undelete_kizeo_users_in`
- **Logs d'export** : `ensure_kizeo_export_logs_table`, `upsert_kizeo_export_log`, `mark_kizeo_export_logs_deleted`
- **Data manuelle** : `upsert_prescription_from_df`, `upsert_secteur_intervention_reb_from_df`, `upsert_parcelle_from_df`
- **Catalogue Kizeo** : `ensure_kizeo_catalog_tables`, `upsert_kizeo_forms_catalog_rows`, `upsert_kizeo_lists_catalog_rows`, `soft_delete_missing_kizeo_forms`, `ensure_kizeo_form_metadata_tables`, `replace_kizeo_form_metadata`

### `payload_models.py`
Tous les modèles Pydantic du projet (`extra="forbid"` sur tous). Chaque script dispatcher importe son modèle ici. Modèles présents :

`NameBuilderPayload`, `ExportKizeoFilePayload`, `RegisterKizeoExportPayload`, `KizeoSchemaBuilderPayload`, `FetchDataKizeoApiPayload`, `MarkActionKizeoApiAsUnreadPayload`, `CreateKizeoUserStructurePayload`, `CreateKizeoListsExcelPayload`, `UpsertDataPostgresqlPayload`, `DdifNameBuilderPayload`, `UpsertDataManuellePayload`, `SyncKizeoCatalogPayload`

Types communs : `FormIdStr`, `DataIdStr`, `BdStr`, `YearSuffixStr`

### `kizeo_mapper.py`
Source de vérité unique pour la correspondance Kizeo → PostgreSQL. Importé par `kizeo_schema_builder.py` et `upsert_data_postgresql.py` pour garantir la cohérence.

- **`clean_name(s)`** — nommage unifié des colonnes/tables (minuscules, `[a-z0-9_]` uniquement)
- **`child_table_name(form_id, sub_name)`** — construit le nom de table enfant
- **`ALWAYS_COLS`** — colonnes forcées dans toutes les tables : `_id`, `_user_id`, `user_ref1`
- **`PROPAGATE_FROM_PARENT`** — colonnes du parent propagées aux lignes enfants : `region`, `unite_d_echantillonnage_ue`, `numero_de_parcelle`, `parcelle_annulee`
- **`pg_type_for_kizeo(field)`** — mapping type Kizeo → type SQL PostgreSQL
- **`parse_form_definition(form_json)`** — parse la définition d'un formulaire Kizeo → `{col: sql_type}` pour parent et sous-formulaires
- **`flatten_kizeo_record(doc)`** — aplatit un JSON Kizeo en `(parent_row, {sub_name: [rows]})`
- **`normalize_bool`, `normalize_numeric`, `normalize_date_like`** — normalisation de valeurs

### `graph_storage.py`
Client Microsoft Graph pour SharePoint. Token OAuth2 `client_credentials` avec cache mémoire et refresh automatique sur 401. Retry automatique sur 423 Locked.

- **`sp_upload_file(local_path, rel_path)`** — upload d'un fichier local vers SharePoint (crée les dossiers si nécessaire)
- **`sp_download_file(rel_path, local_path)`** — téléchargement depuis SharePoint
- **`sp_ensure_folder(rel_dir)`** — crée récursivement un dossier SharePoint
- **`sp_list_children(rel_dir)`** — liste le contenu d'un dossier SharePoint
- **`sp_delete_file(rel_path)`** — supprime un fichier SharePoint (retourne `False` si 404)
- **`sp_put_text(rel_path, text)`** — upload d'un contenu texte

Toutes les fonctions travaillent avec des chemins **relatifs sous `GRAPH_SP_ROOT_DIR`** (par défaut `General`). Ne pas préfixer les chemins avec `General\`.

### `dbf_writer.py`
Utilitaire bas niveau pour l'écriture de fichiers DBF (FoxPro). Copie un template DBF, écrit les données des lignes dans les colonnes correspondantes (matching par nom de colonne avant virgule, en majuscules), met à jour le compteur de records et l'EOF. Utilisé uniquement par `build_ddif_exports.py`.

### `liste_kizeo_lists.py`
Registre statique des IDs de listes Kizeo par `year_suffix` et nom de feuille. Édité manuellement pour maintenir la correspondance feuille Excel → ID liste Kizeo. Utilisé par `create_kizeo_lists_json.py` comme module de mapping.

API publique : `get_list_id(year_suffix, sheet_name)`, `is_known_sheet(year_suffix, sheet_name)`, `all_sheets(year_suffix)`

---

## Scripts dispatcher Flask

Ces scripts ont tous `handle(payload: dict, logger) -> dict` et sont appelés par `run_flask_server.py` via le header `X-Script-Name`.

### `sync_kizeo_catalog.py`
**Catalogue Kizeo unifié.** Remplace les anciens `create_kizeo_catalog_structure.py`, `inspect_kizeo_catalog_details.py`, `sync_kizeo_form_metadata_from_files.py`, `sync_kizeo_catalog_full.py`.

Deux modes selon la présence de `form_id` dans la payload :

- **Global** (`form_id` absent) : appelle `/forms` + `/lists` + détails de chaque form et list → upsert dans `app.kizeo_forms_catalog`, `app.kizeo_lists_catalog`, soft-delete des forms/lists disparues, remplace les métadonnées (fields + exports + list_links) pour tous les forms
- **Single form** (`form_id` présent) : appelle uniquement `/forms/{form_id}` → upsert catalog + métadonnées pour ce seul formulaire. Appelé par `kizeo_schema_builder.py` avant la construction du schéma DDL.

Paramètres payload : `bd` (requis), `form_id` (optionnel), `load_pg` (bool, défaut true), `save_raw` (bool, dump JSON brut sur disque), `output_dir`

ENV : `KIZEO_TOKEN`, `KIZEO_API_URL`

### `kizeo_schema_builder.py`
**Crée ou met à jour le schéma PostgreSQL DDL d'un formulaire Kizeo.** Pipeline complet :

1. Appelle `sync_kizeo_catalog.handle()` pour garantir que le catalogue est à jour (mode single_form, avec `include_raw=True` pour éviter un second GET)
2. Appelle `kizeo_mapper.parse_form_definition()` sur le JSON brut → `{col: sql_type}` parent + sous-formulaires
3. Construit un DDL idempotent (`CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`)
4. Applique le DDL via `app.ensure_rls_for_table()` qui active aussi le Row Level Security
5. Appelle `fetch_data_kizeo_api.handle()` pour récupérer les données initiales

Le schéma PostgreSQL créé correspond au `form_id` (ex : schéma `"880205"`, table principale `"880205"`, tables enfants `"880205_<subform_name>"`).

Paramètres payload : `form_id`, `bd`, `export_name`, `user_id`, `year_suffix`, et optionnels : `ue`, `region`, `form_name`, `export_type`, `upsert_mode`

### `fetch_data_kizeo_api.py`
**Télécharge les données d'un formulaire Kizeo depuis l'API** (entrées non lues ou un `data_id` précis) et les écrit en JSON dans `run_dir/data/`. Appelle ensuite directement `upsert_data_postgresql.handle()`.

Deux modes :
- **Batch** : récupère toutes les entrées non lues pour l'action `import_pg` (plusieurs JSON → mode batch forcé côté upsert)
- **Single** : récupère un `data_id` précis

Paramètres payload : `form_id`, `bd`, `run_dir`, et optionnels : `data_id`, `upsert_mode`, `export_name`, `user_id`, `year_suffix`, `ue`, `region`, `export_type`

### `upsert_data_postgresql.py`
**Lit les JSON de `run_dir/data/*.json` et upserte dans PostgreSQL** (table parent + tables enfants des sous-formulaires).

Gère aussi les suppressions si `deleted_ids.txt` ou `summary.json.deleted_ids` est présent.

Deux modes d'upsert :
- **`single`** : commit par enregistrement, comportement robuste historique
- **`batch`** : pre-scan global des colonnes, préparation DDL en une passe, SAVEPOINTs, commit toutes les 25 entrées. Forcé automatiquement si `docs_count > 1`.

Après les upserts réussis, écrit `ids_to_mark_read.txt` et appelle `mark_action_kizeo_api.py` en subprocess pour marquer les IDs comme lus côté Kizeo.

Paramètres payload : `form_id`, `bd`, `run_dir`, `db_schema` (ou `schema`), optionnel `upsert_mode`

### `name_builder.py`
**Construit le chemin SharePoint relatif (mode 100% Graph) pour un export Kizeo** et appelle `download_kizeo_file.handle()`.

Résout depuis la BD : `export_id`, `user_ref1`, `coop_code` (= `app.coops.directory`), `form_name`.

Structure du chemin final (relatif sous `General/`) :
```
<coop_code>/<year_suffix>/<form_name>/[<region>/][<ue>/]
```

`app.coops.directory` contient désormais le **code coop** (ex: `RBT`), pas un chemin de fichier.

Paramètres payload : `form_id`, `data_id`, `export_name`, `user_id`, `bd`, `year_suffix`, et optionnels : `ue`, `region`, `form_name`, `export_type`

### `download_kizeo_file.py`
*(Anciennement `export_kizeo_file.py` — renommé)*

**Télécharge un export Kizeo (Excel ou PDF) depuis l'API Kizeo** et **l'uploade vers SharePoint via Graph**. Utilise un fichier local temporaire pour l'upload. Pour les exports Excel avec export_type compatible PDF, crée aussi un job `job_*.json` dans `pdf_queue/` pour la conversion par `excel_worker.py`.

Paramètres payload : ceux fournis par `name_builder.py` + `output_dir` (chemin SharePoint relatif sans `General\`)

### `register_kizeo_export.py`
**Enregistre un export dans `app.kizeo_export_logs`.** Deux modes selon le champ `action` (ou `mode`) de la payload :

- **Insert/upsert** : log l'export (form_id, data_id, export_id, user_ref1, output_path, size_bytes, etc.)
- **Delete** : supprime le fichier SharePoint via `graph_storage.sp_delete_file()` + marque `deleted_at` dans les logs

Dans les deux cas, si `ue`, `region`, `output_dir`, `form_id`, `year_suffix` et `form_name` sont tous présents, déclenche `build_rapport_execution.build_from_register_payload()` pour recalculer le rapport d'exécution de l'UE.

### `build_rapport_execution.py`
**Génère ou recalcule un rapport d'exécution Excel (`RE_<UE>.xlsx`)** pour une UE donnée.

Pipeline :
1. Télécharge le modèle Excel depuis SharePoint (`1-Gestion/rapport_execution/<year_suffix>/<form_name>/<region>/`)
2. Résout le schéma PostgreSQL contenant les données du formulaire
3. Requête les données : table parent (filtré sur `user_ref1`, `ue`, `parcelle_annulee=false`) + tables enfants + `app.prescriptions` + `app.secteur_intervention_reb`
4. Remplit les feuilles Excel dont le nom correspond aux tables (feuille parent = `form_id`, feuilles enfants = nom de table sans préfixe `<form_id>_`)
5. Sauvegarde localement en temp, uploade vers `output_dir/RE_<UE>.xlsx` sur SharePoint

Le RE est **recalculé** (jamais supprimé) même lors d'un delete d'export, reflétant l'état courant de la BD.

Également exposé comme `handle(payload, logger)` pour appel direct via le dispatcher.

### `ddif_name_builder.py`
**Construit le chemin SharePoint pour un export DDIF** (parallèle à `name_builder.py` pour la chaîne DDIF).

Résout depuis la BD : `user_ref1`, `coop_code`, `form_name` (via `fetch_form_name_for_form_id`, sans sanitization — nom exact de la BD). Appelle ensuite `build_ddif_exports.py` comme subprocess.

Structure du chemin (relatif sous `General/`) :
```
<coop_code>/<year_suffix>/<form_name>/<region>/[<ue>/]
```

Paramètres payload : `form_id`, `data_id`, `user_id`, `bd`, `year_suffix`, `region`, et optionnels : `ue`, `form_name`

### `upsert_data_manuelle_db.py`
**Importe les fichiers Excel "data manuelle" dans PostgreSQL.** Feuilles ciblées par défaut : `prescription`, `parcelle`, `secteur_intervention_reb`.

Pipeline :
1. Récupère les chemins de fichiers depuis `app.get_data_manuelle_files(year_suffix)` (BD)
2. Télécharge chaque fichier depuis SharePoint via Graph
3. Merge les feuilles identiques entre tous les workbooks (union des colonnes)
4. Génère un Excel de prévisualisation (`data_manuelle_preview.xlsx`)
5. Pousse vers PostgreSQL via `safe_db.upsert_<sheet>_from_df()` avec retry

Quand appelé via le dispatcher Flask, le push DB est toujours activé.

Paramètres payload : `bd`, `year_suffix`, optionnel `only_sheets`

### `create_kizeo_lists_excel.py`
**Stage 1 du pipeline listes Kizeo.** Merge les feuilles de données manuelle depuis SharePoint et écrit un fichier Excel par feuille dans un sous-dossier horodaté. Appelle ensuite `create_kizeo_lists_json.py` comme subprocess.

N'importe rien en base PostgreSQL — uniquement préparation des données pour les listes Kizeo.

Paramètres payload : `bd`, `year_suffix`, optionnel `only_sheets`

### `create_kizeo_user_structure.py`
**Synchronise les utilisateurs Kizeo vers PostgreSQL** (table `app.kizeo_users` ou configurable via `PG_SCHEMA_USER`/`PG_TABLE_USER`).

1. Appelle `GET /users` avec pagination (par tranches de 500)
2. Écrit JSON + CSV + XLSX (si pandas disponible) dans `output_dir`
3. Upsert dans PostgreSQL avec soft-delete des utilisateurs disparus

Paramètres payload : `bd`, optionnels : `load_pg`, `output_dir`, `json_name`, `csv_name`, `xlsx_name`

ENV : `KIZEO_TOKEN`, `KIZEO_API_URL`, `PG_SCHEMA_USER`, `PG_TABLE_USER`, `OUTPUT_DIR_CREATE_KIZEO_USER_STRUCTURE`

### `mark_action_kizeo_api_as_unread.py`
**Remet des entrées Kizeo en statut "non lu"** pour une action donnée (par défaut : `import_pg`). Récupère tous les `_id` depuis la table principale du formulaire (`<form_id>.<form_id>`) et les envoie à l'endpoint `markasunreadbyaction` par paquets de 100.

Disponible à la fois comme dispatcher Flask (`handle()`) et comme script CLI.

Paramètres payload : `bd`, `form_id`, optionnels : `action`, `limit`, `dry_run`

---

## Scripts CLI uniquement (pas de handle Flask)

### `mark_action_kizeo_api.py`
**Marque des entrées Kizeo comme lues** pour une action donnée (par défaut : `import_pg`). Appelé comme subprocess par `upsert_data_postgresql.py` après les upserts réussis.

Prend `--form_id`, `--ids_file` (fichier `ids_to_mark_read.txt`), `--bd`, `--action`. Envoie les IDs par paquets avec retry. Retourne un JSON sur stdout.

**N'a pas de `handle()` Flask** — subprocess uniquement.

---

## Scripts appelés uniquement en subprocess

### `build_ddif_exports.py`
**Génère les fichiers DBF DDIF pack-driven et les uploade vers SharePoint.** Appelé par `ddif_name_builder.py`.

Pour chaque template `.dbf` dans `scripts/ddif/<year_suffix>/<form_name>/<region>/templates/` :
1. Lit la config du pack (`config.yaml`) pour savoir quelle fonction SQL appeler
2. Drop + re-installe la fonction SQL depuis `sql/<X>.sql`
3. Appelle la fonction : `SELECT * FROM <func>(year_suffix, region, ue, cfg::jsonb, form_id)`
4. Écrit les lignes dans une copie du template DBF via `dbf_writer.write_values_to_dbf_copy()`
5. Uploade vers `output_dir/ddif/<template>.dbf` sur SharePoint

Les templates sans SQL configurée sont uploadés vides (non bloquant).

### `create_kizeo_lists_json.py`
**Stage 2 du pipeline listes Kizeo.** Convertit les fichiers Excel (un par feuille) en JSONs formatés pour l'API Kizeo. Gestion schema-driven des colonnes :
- `user_ref1` → premier segment verbatim (ex: `[[user_ref1=RBT]]`)
- `level_label*` → hiérarchie avec `\` comme séparateur de niveau
- `ref*` → segments `valeur:valeur`

Nomme chaque JSON avec l'ID de liste Kizeo résolu via `liste_kizeo_lists.py` (ou un module de mapping personnalisé). Appelle ensuite `upload_lists_to_kizeo.py`.

### `upload_lists_to_kizeo.py`
**Stage 3 du pipeline listes Kizeo.** Uploade les JSONs de listes vers l'API Kizeo via `PUT /lists/{list_id}`. Mécanisme de verrouillage par fichier pour éviter les uploads concurrents sur la même liste. Sauvegarde les items existants avant remplacement (backup dans `listes/backups/`).

---

## Worker standalone

### `excel_worker.py`
**Worker Excel Desktop Windows** qui tourne dans la session utilisateur (obligatoire pour piloter Excel COM).

Boucle infinie qui :
1. Scan `pdf_queue/job_*.json` toutes les N secondes (`WORKER_SLEEP_SECONDS`, défaut 3)
2. Pour chaque job `status=pending` :
   - Télécharge l'Excel depuis SharePoint (`sp_excel_rel_path`)
   - Convertit en PDF via Excel Desktop (`excel_to_pdf.convert_excel_to_pdf()`) — feuille cible : `Parcelle`
   - Uploade le PDF vers SharePoint (`sp_pdf_rel_path`)
   - Appelle `register_kizeo_export.py` en subprocess
   - Archive le job dans `pdf_queue/archive/` (ou `error/`)
3. Écrit un heartbeat JSON (`excel_worker_heartbeat.json`) à chaque iteration

Instance unique garantie par verrou `msvcrt.locking`. Les jobs `sp_excel_rel_path`/`sp_pdf_rel_path` sont créés par `download_kizeo_file.py`.

---

## Scripts infra / planifiés

### `rotate_make_to_flask_auth.py`
**Rotation quotidienne de la clé d'authentification Make → Flask.** Exécuté par le Planificateur de tâches Windows.

1. Lit le token 1Password Service Account depuis `OP_SERVICE_ACCOUNT_TOKEN` (env) ou Windows Credential Manager
2. Lit l'ancienne clé (`MAKE_TO_FLASK_AUTH`) depuis le vault 1Password via `op.exe`
3. Génère une nouvelle clé (48 caractères, lettres+chiffres+symboles) dans 1Password
4. Pousse la nouvelle clé dans le Make Data Store `runtime_secrets/flask_auth_key`
5. Écrit `make_auth.json` pour permettre à Flask d'accepter les deux clés pendant une fenêtre de grâce (30 min)

---

## Scripts debug / test

### `test_graph.py`
Script de diagnostic manuel pour tester la connectivité Microsoft Graph. Charge `.env`, obtient un token, effectue quelques requêtes Graph de vérification. Usage : exécution manuelle uniquement, pas dans le pipeline.

---

## Notes importantes sur les scripts renommés/supprimés

| Ancien nom | Statut | Remplacé par |
|---|---|---|
| `kizeo_schema_builder_export.py` | Supprimé | `sync_kizeo_catalog.py` |
| `export_kizeo_file.py` | Renommé | `download_kizeo_file.py` |
| `create_kizeo_lists_structure.py` | Supprimé | `create_kizeo_user_structure.py` (utilisateurs) + `sync_kizeo_catalog.py` (catalogue) |

Tout code ou documentation qui référence ces anciens noms est obsolète.
