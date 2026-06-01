# Schéma PostgreSQL
*Organisation des données pour le pipeline Kizeo → FQCF*

Ce document décrit la structure logique de la base PostgreSQL utilisée par les scripts :
- schémas par formulaire Kizeo,
- schéma transversal `app` (13 tables),
- principes de sécurité (RLS par coop).

---

# 1. Vue globale

```text
postgresql
 ├── app
 │    ├── coops
 │    ├── kizeo_users
 │    ├── kizeo_forms
 │    ├── kizeo_form_exports
 │    ├── kizeo_form_fields
 │    ├── kizeo_form_lists
 │    ├── kizeo_lists
 │    ├── kizeo_export_logs
 │    ├── kizeo_tombstones
 │    ├── data_manuelle_files
 │    ├── prescriptions
 │    ├── parcelles
 │    ├── secteur_intervention_reb
 │    └── exports  ← legacy, plus utilisée (voir note)
 ├── 880205
 │    ├── 880205          (table parent)
 │    ├── 880205_sous1    (table enfant)
 │    └── ...
 ├── 798333
 │    └── ...
 └── ...
```

> **`app.exports` (legacy)** : table créée par l'ancien `kizeo_schema_builder_export.py` (code mort dans `scripts/expires/`). Aucun script actif ne l'utilise. Remplacée par `app.kizeo_form_exports`. Peut être droppée.

---

# 2. Schémas par formulaire (`form_id`)

Pour chaque formulaire Kizeo :
- Un **schéma PostgreSQL** nommé par son `form_id` (ex. `880205`)
- Une **table parent** portant le même nom (`880205`)
- Une **table par sous-formulaire** (`880205_<nom_sous_form>`)

## 2.1. Table parent

| Colonne | Type | Description |
|---|---|---|
| `_id` | bigint | `data_id` Kizeo (clé primaire) |
| `_user_id` | bigint | ID utilisateur Kizeo |
| `user_ref1` | text | Code coop (clé RLS) |
| champs métier | divers | Champs du formulaire Kizeo |

Colonnes propagées depuis le parent dans les sous-formulaires : `region`, `unite_d_echantillonnage_ue`, `numero_de_parcelle`, `parcelle_annulee`.

## 2.2. Tables enfants (sous-formulaires)

| Colonne | Type | Description |
|---|---|---|
| `_id` | bigint | ID du sous-enregistrement |
| `_parent_id` | bigint | `_id` de la table parent |
| `_user_id` | bigint | ID utilisateur Kizeo |
| `user_ref1` | text | même coop que le parent |
| champs divers | divers | Contenu du sous-formulaire |

---

# 3. Schéma `app`

## 3.1. `app.coops`

Référentiel des coopératives. Source de vérité pour le chemin SharePoint de chaque coop.

| Colonne | Type | Description |
|---|---|---|
| `coop_code` | text (PK) | Code unique de la coop (ex: `RBT`, `CFNC`, `FQCF`) |
| `coop_name` | text | Nom complet |
| `directory` | text | Dossier SharePoint de base (ex: `CFNC`, `CFGaspesie`, `1-Gestion`) |
| `user_ref1` | text | Code coop utilisé pour la RLS (= `coop_code` en général) |
| `login_name` | text | Nom de connexion ODBC (minuscules) |
| `created_at` | timestamptz | Date de création |
| `updated_at` | timestamptz | Date de mise à jour |

> `directory` est presque toujours identique à `coop_code` : ex. `CFG` → `CFG`, `CFHPV` → `CFHautPlanVert`, sauf pour `FQCF` → `1-Gestion`. C'est la valeur utilisée pour construire le chemin SharePoint.

---

## 3.2. `app.kizeo_users`

Lien entre les utilisateurs Kizeo et les coops. Alimentée par `create_kizeo_user_structure.py`.

| Colonne | Type | Description |
|---|---|---|
| `kizeo_user_id` | bigint | ID utilisateur dans Kizeo |
| `user_ref1` | text | Code coop (clé RLS) |
| `name` | text | Nom / prénom |
| `email` | text | Adresse email |
| `is_active` | boolean | Actif / inactif (soft-delete) |

Utilisée par `name_builder.py` et `ddif_name_builder.py` pour résoudre `user_ref1` depuis `user_id`.

---

## 3.3. Catalogue Kizeo (`kizeo_forms`, `kizeo_form_exports`, `kizeo_form_fields`, `kizeo_form_lists`, `kizeo_lists`)

Alimentées par `sync_kizeo_catalog.py`. Source de vérité pour les métadonnées des formulaires Kizeo.

| Table | Contenu |
|---|---|
| `app.kizeo_forms` | Liste des formulaires (form_id, name, update_time…) |
| `app.kizeo_form_exports` | Exports disponibles par formulaire (export_id, name_excel, name_pdf, form_name…) |
| `app.kizeo_form_fields` | Définition des champs de chaque formulaire |
| `app.kizeo_form_lists` | Liens entre formulaires et listes Kizeo |
| `app.kizeo_lists` | Catalogue des listes Kizeo disponibles |

`app.kizeo_form_exports` est utilisée par `name_builder.py` pour résoudre l'`export_id` depuis l'`export_name`.

---

## 3.4. `app.kizeo_export_logs`

Journalise chaque export Excel/PDF effectué. Alimentée par `register_kizeo_export.py`.

| Colonne | Type | Description |
|---|---|---|
| `form_id` | text | ID formulaire |
| `data_id` | bigint | ID enregistrement Kizeo |
| `export_id` | text | ID export Kizeo |
| `form_name` | text | Nom du formulaire |
| `export_type` | text | `excel` ou `pdf` |
| `user_ref1` | text | Code coop |
| `output_dir` | text | Dossier SharePoint relatif (sous `General/`) |
| `output_path` | text | Chemin SharePoint relatif complet du fichier |
| `filename` | text | Nom du fichier |
| `size_bytes` | bigint | Taille en octets |
| `year_suffix` | text | Clé d'année (ex: `2025-2026`) |
| `ue` | text | Unité d'échantillonnage |
| `region` | text | Code région |
| `created_at` | timestamptz | Première exportation |
| `updated_at` | timestamptz | Dernière réexportation |
| `deleted_at` | timestamptz | Rempli en mode DELETE |

---

## 3.5. `app.kizeo_tombstones`

Trace des enregistrements supprimés côté Kizeo. Alimentée par `upsert_data_postgresql.py`.

| Colonne | Type | Description |
|---|---|---|
| `form_id` | text | ID formulaire |
| `data_id` | bigint | ID de l'enregistrement supprimé |
| `deleted_at` | timestamptz | Date de suppression |

---

## 3.6. `app.data_manuelle_files`

Liste des fichiers Excel "données manuelles" sur SharePoint, par coop et par année. Utilisée par `upsert_data_manuelle_db.py` et `create_kizeo_lists_excel.py` via `app.get_data_manuelle_files(year_suffix)`.

| Colonne | Type | Description |
|---|---|---|
| `coop_code` | text | Code de la coop |
| `year_suffix` | text | Clé d'année (ex: `2025-2026`) |
| `file_path` | text | Chemin SharePoint relatif du fichier |
| `enabled` | boolean | Fichier actif pour la fusion |
| `created_at` | timestamptz | Date d'ajout |

---

## 3.7. Tables données manuelles (`prescriptions`, `parcelles`, `secteur_intervention_reb`)

Alimentées par `upsert_data_manuelle_db.py` à partir des fichiers SharePoint data manuelle.

| Table | Feuille source |
|---|---|
| `app.prescriptions` | feuille `prescription` |
| `app.parcelles` | feuille `parcelle` |
| `app.secteur_intervention_reb` | feuille `secteur_intervention_reb` |

---

## 3.8. `app.script_runs`

Table d'audit des exécutions du dispatcher Flask. Alimentée automatiquement par `run_flask_server.py`.

| Colonne | Type | Description |
|---|---|---|
| `run_id` | UUID (PK) | = `request_id` du dispatcher |
| `timestamp_start` | timestamptz | Heure de réception de la requête |
| `timestamp_end` | timestamptz | Heure de fin du script |
| `duration_ms` | integer | Durée totale (lock wait + exécution) |
| `status` | text | `running` → `ok` ou `error` |
| `script_name` | text | Nom du script déclenché |
| `source_ip` | text | IP de Make (appelant) |
| `user_agent` | text | User-Agent HTTP |
| `payload_raw` | jsonb | Payload complète (secrets redactés) |
| `payload_sanitized` | jsonb | Payload courte : bd, form_id, data_id, user_id, ue, region, year_suffix |
| `user_id` | text | ID utilisateur Kizeo |
| `user_ref1` | text | Code coop résolu depuis `app.kizeo_users` |
| `form_id` | text | ID formulaire |
| `form_name` | text | Nom lisible du formulaire |
| `data_id` | text | ID enregistrement Kizeo |
| `ue` | text | Unité d'échantillonnage |
| `region` | text | Région géographique |
| `year_suffix` | text | Suffixe d'année (ex: `2025-2026`) |
| `result_summary` | jsonb | Dict de retour du script (`handle()`) |
| `error_message` | text | Message d'erreur condensé |
| `error_traceback` | text | Traceback Python complet (si exception) |

> `status='running'` indique un script bloqué ou crashé sans UPDATE final.

---

# 4. RLS (Row-Level Security) & rôles

## 4.1. Principe général

Toutes les tables contenant des données coop ont un champ `user_ref1`. Une politique RLS est appliquée :

```sql
USING (user_ref1 = app.current_coop())
```

`app.current_coop()` lit `current_setting('app.user_ref1')` — variable de session positionnée à la connexion selon le rôle PostgreSQL.

## 4.2. Rôles par coop

Chaque coop dispose d'un rôle PostgreSQL dédié (ex: `coop_ro_abifor`, `coop_ro_cfnc`…) avec `SELECT` sur les schémas pertinents et RLS activée.

## 4.3. Application sur les tables formulaires

```sql
ALTER TABLE "880205"."880205" ENABLE ROW LEVEL SECURITY;

CREATE POLICY p_880205_rls
ON "880205"."880205"
USING (user_ref1 = app.current_coop());
```

Idem pour chaque sous-formulaire.

---

# 5. Connexions ODBC / BI

Un utilisateur PostgreSQL par coop, associé à son rôle :
- ex. utilisateur `abifor` → rôle `coop_ro_abifor`
- Clients : Excel, Power BI, QGIS, etc.
- Grâce à RLS, chaque coop ne voit que ses propres données.

---

# 6. Bonnes pratiques d'évolution du schéma

- Ne jamais supprimer une colonne sans vérifier les scripts qui l'utilisent.
- Préférer ajouter des colonnes plutôt que casser un pipeline existant.
- Documenter les nouvelles tables / colonnes dans ce fichier.

---

# 7. Voir aussi

- [architecture.md](architecture.md) — vue globale du système
- [pipeline_kizeo.md](pipeline_kizeo.md) — ingestion des formulaires
- [pipeline_exports.md](pipeline_exports.md) — gestion des exports PDF/Excel
- [pipeline_data_manuelle.md](pipeline_data_manuelle.md) — import données manuelles
- [scripts_overview.md](scripts_overview.md) — rôle de chaque script
- [security_env.md](security_env.md) — variables d'environnement & sécurité
