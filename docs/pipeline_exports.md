# Pipeline des exports Kizeo (Excel & PDF)

Ce document décrit le pipeline complet permettant de :
- résoudre le bon export Kizeo et construire le chemin SharePoint,
- télécharger le fichier depuis Kizeo et l'uploader vers SharePoint,
- journaliser l'opération dans PostgreSQL,
- générer automatiquement un rapport d'exécution Excel pour l'UE,
- convertir l'Excel en PDF via le worker Desktop.

**Architecture de stockage : 100% Microsoft Graph / SharePoint.** Aucun fichier n'est écrit sur disque local de façon permanente. Tous les chemins sont relatifs sous `GRAPH_SP_ROOT_DIR` (= `General/`). Ne jamais préfixer avec `General\`.

---

## Scripts impliqués

| Script | Rôle | Appel |
|---|---|---|
| `sync_kizeo_catalog.py` | Synchronise le catalogue des exports Kizeo → PostgreSQL | Flask dispatcher (ou auto via `kizeo_schema_builder`) |
| `name_builder.py` | Résout le chemin SharePoint et appelle `download_kizeo_file` | Flask dispatcher (Make) |
| `download_kizeo_file.py` | Télécharge depuis Kizeo + uploade vers SharePoint | Appelé par `name_builder` |
| `register_kizeo_export.py` | Journalise l'export dans `app.kizeo_export_logs` | Flask dispatcher (Make) ou appelé par `excel_worker` |
| `build_rapport_execution.py` | Génère `RE_<UE>.xlsx` depuis les données PostgreSQL | Déclenché automatiquement par `register_kizeo_export` |
| `excel_worker.py` | Convertit Excel → PDF via Excel Desktop, uploade le PDF | Worker standalone (boucle infinie, session utilisateur) |

---

## Vue générale

```
Make
 │
 ▼
name_builder.py
 │  Résout: export_id, user_ref1, coop_code, form_name, output_dir
 │
 ▼
download_kizeo_file.py
 │  GET Kizeo API → upload SharePoint (Excel)
 │  Crée job_*.json dans pdf_queue/ (si PDF demandé)
 │
 ├──► SharePoint: General/<coop>/<year>/<form>/[region/][ue/]/fichier.xlsx
 │
 ▼
register_kizeo_export.py  ◄── (Make, séparément)
 │  INSERT/UPDATE app.kizeo_export_logs
 │
 ├──► build_rapport_execution.py  (si ue+region+form_id+year_suffix+form_name présents)
 │     └──► SharePoint: General/<coop>/<year>/<form>/<region>/<ue>/RE_<UE>.xlsx
 │
excel_worker.py  (boucle autonome)
 │  Lit pdf_queue/job_*.json (status=pending)
 │  Télécharge xlsx SharePoint → convert Excel Desktop → PDF
 │  Upload PDF SharePoint
 └──► register_kizeo_export.py (subprocess)
```

---

## Étape 0 — Catalogue des exports : `sync_kizeo_catalog.py`

Avant d'exporter, les métadonnées des formulaires et de leurs exports doivent être en base. C'est le rôle de `sync_kizeo_catalog.py`.

Ce script appelle l'API Kizeo et synchronise dans PostgreSQL :
- `app.kizeo_forms_catalog` — liste des formulaires (form_id, name, update_time…)
- `app.kizeo_form_exports` — exports disponibles (export_id, name_excel, name_pdf, form_name…)
- `app.kizeo_form_fields` — définition des champs de chaque formulaire
- `app.kizeo_lists_catalog` — listes Kizeo disponibles

**En mode global** (payload sans `form_id`) : synchronise tous les formulaires et listes.  
**En mode single_form** (payload avec `form_id`) : synchronise uniquement ce formulaire — c'est ce mode qui est appelé automatiquement par `kizeo_schema_builder.py` avant la construction du schéma DDL.

`name_builder.py` utilise `app.kizeo_form_exports` pour résoudre l'`export_id` à partir du `export_name` fourni par Make.

---

## Étape 1 — Construction du chemin SharePoint : `name_builder.py`

Point d'entrée Make pour tout export. Ce script résout le contexte depuis la BD puis délègue à `download_kizeo_file`.

### Payload Make (exemple)

```json
{
  "form_id": "880205",
  "data_id": "177314594",
  "export_name": "Formulaire de nettoiement avant traitement BSLG",
  "user_id": "562703",
  "bd": "chlorofile2",
  "year_suffix": "2025-2026",
  "ue": "2023-11161_-ELS3-502",
  "region": "GIM"
}
```

### Résolution PostgreSQL

| Information | Table source | Clé de résolution |
|---|---|---|
| `export_id` | `app.kizeo_form_exports` | `form_id` + `export_name` (ILIKE) |
| `user_ref1` | `app.kizeo_users` | `user_id` |
| `coop_code` | `app.coops` | `user_ref1` (colonne `directory`) |
| `form_name` | `app.kizeo_form_exports` | `form_id` |

> `app.coops.directory` contient maintenant le **code coop** (ex: `RBT`, `CFNC`), pas un chemin de fichier. C'est la migration de l'ancien système OneDrive local vers Graph.

### Structure du chemin SharePoint (relatif sous `General/`)

```
<coop_code>/<year_suffix>/<form_name>/                         (sans région ni UE)
<coop_code>/<year_suffix>/<form_name>/<ue>/                    (UE seul)
<coop_code>/<year_suffix>/<form_name>/<region>/                (région seul)
<coop_code>/<year_suffix>/<form_name>/<region>/<ue>/           (région + UE)
```

Exemples concrets (valeurs relatifs — Graph ajoute `General/` devant) :

```
RBT/2025-2026/Formulaire nettoyage/01/2023-11161_-ELS3-502/
CFNC/2025-2026/Inventaire parcelle/MAU/
```

### Payload enrichi transmis à `download_kizeo_file`

`name_builder` ajoute au payload d'origine :
- `export_id` — résolu depuis `app.kizeo_form_exports`
- `user_ref1` — résolu depuis `app.kizeo_users`
- `coop_directory` — code coop (ex: `RBT`)
- `form_name` — nom du formulaire
- `output_dir` — chemin SharePoint relatif construit (sans `General\`)

---

## Étape 2 — Téléchargement et upload SharePoint : `download_kizeo_file.py`

*(Anciennement `export_kizeo_file.py` — renommé lors de la migration Graph)*

Ce script télécharge le fichier depuis l'API Kizeo et l'uploade directement vers SharePoint via Microsoft Graph. Aucun fichier permanent en local.

### Endpoints Kizeo

**Excel :**
```
GET /rest/v3/forms/{form_id}/data/{data_id}/exports/{export_id}
```

**PDF :**
```
GET /rest/v3/forms/{form_id}/data/{data_id}/exports/{export_id}/pdf
```

Le nom du fichier est lu depuis l'en-tête HTTP `Content-Disposition: attachment; filename="..."` — Kizeo fournit le vrai nom, le script ne renomme pas.

### Stockage SharePoint

Le fichier est uploadé vers :
```
General/<output_dir>/<filename>
```
via `graph_storage.sp_upload_file()`. Les dossiers intermédiaires sont créés automatiquement si nécessaire.

### Génération du job PDF

Si la configuration le requiert (export Excel + conversion PDF demandée), `download_kizeo_file` crée un fichier `pdf_queue/job_<ts>.json` avec :
- `sp_excel_rel_path` — chemin SharePoint du fichier Excel uploadé
- `sp_pdf_rel_path` — chemin SharePoint cible pour le PDF
- `data_id`, `export_id`, `user_ref1`, `bd`, etc. — contexte nécessaire pour `register_kizeo_export`

Ce job sera traité de façon asynchrone par `excel_worker.py`.

---

## Étape 3 — Journalisation : `register_kizeo_export.py`

Ce script consigne l'export dans la table `app.kizeo_export_logs`. Il peut être appelé par Make directement (pour l'Excel), ou par `excel_worker` en subprocess (pour le PDF).

### Table `app.kizeo_export_logs` (colonnes principales)

| Colonne | Description |
|---|---|
| `form_id` | ID du formulaire |
| `data_id` | ID de l'enregistrement Kizeo |
| `export_id` | ID de l'export Kizeo |
| `form_name` | Nom du formulaire |
| `export_type` | `excel` ou `pdf` |
| `user_ref1` | Code coop de l'utilisateur |
| `output_dir` | Dossier SharePoint relatif |
| `output_path` | Chemin complet SharePoint du fichier |
| `filename` | Nom du fichier |
| `size_bytes` | Taille en octets |
| `year_suffix` | Clé d'année |
| `ue` | Unité d'échantillonnage |
| `region` | Région |
| `created_at` | Première exportation |
| `updated_at` | Dernière réexportation |
| `deleted_at` | Rempli en mode DELETE |

### Mode INSERT / UPSERT

Lors d'un export normal : INSERT si première fois, UPDATE sinon. Une seule ligne par `(data_id, export_id)`.

### Mode DELETE

Activé par un champ `action` ou `mode` = `delete` dans la payload.

Ce mode :
1. Supprime le fichier sur **SharePoint** via `graph_storage.sp_delete_file(rel_path)` — le fichier disparaît réellement du cloud
2. Met à jour `deleted_at` dans `app.kizeo_export_logs` (soft-delete BD)

### Déclenchement automatique du rapport d'exécution

Après chaque INSERT, UPDATE **et** DELETE, si les champs `ue`, `region`, `output_dir`, `form_id`, `year_suffix` et `form_name` sont tous présents, `register_kizeo_export` appelle automatiquement `build_rapport_execution.build_from_register_payload()`.

Le rapport est donc **toujours recalculé** pour refléter l'état courant de la base — qu'on ajoute ou qu'on supprime un export.

---

## Étape 4 — Rapport d'exécution : `build_rapport_execution.py`

Ce script génère ou met à jour le fichier `RE_<UE>.xlsx` pour une UE donnée.

### Ce qu'il fait

1. Cherche le modèle Excel dans SharePoint :
   ```
   General/1-Gestion/rapport_execution/<year_suffix>/<form_name>/<region>/*.xlsx
   ```
2. Se connecte à PostgreSQL, résout le schéma contenant les données du formulaire
3. Requête les données filtrées sur `user_ref1`, `ue`, `parcelle_annulee = false` :
   - table parent (`<form_id>`)
   - tables enfants (`<form_id>_<subform>`)
   - `app.prescriptions`
   - `app.secteur_intervention_reb`
4. Remplit les feuilles Excel dont le nom correspond aux tables
5. Sauvegarde en fichier temp local, uploade vers SharePoint :
   ```
   General/<output_dir>/RE_<UE>.xlsx
   ```

> Le modèle Excel n'est jamais modifié — seul le fichier résultat est uploadé.

---

## Étape 5 — Conversion PDF : `excel_worker.py`

Worker Windows qui tourne en permanence dans la session utilisateur (nécessaire pour piloter Excel Desktop via COM).

### Cycle de vie d'un job PDF

```
download_kizeo_file.py
 └── crée pdf_queue/job_<ts>.json  (status: pending)

excel_worker.py  (toutes les 3 secondes)
 └── détecte job pending
     ├── status → processing
     ├── sp_download_file(sp_excel_rel_path) → tmp local
     ├── convert_excel_to_pdf(tmp_xlsx) → tmp local PDF  [via Excel Desktop, feuille "Parcelle"]
     ├── sp_upload_file(tmp_pdf, sp_pdf_rel_path) → SharePoint
     ├── appelle register_kizeo_export.py --payload ... (subprocess)
     ├── status → done
     └── déplace le job dans pdf_queue/archive/
```

En cas d'erreur à n'importe quelle étape : `status → error`, job déplacé dans `pdf_queue/error/`.

### Heartbeat

Un fichier `logs/excel_worker_heartbeat.json` est réécrit à chaque boucle avec `timestamp_utc`, `pid`, `hostname`, `status`. Permet de détecter si le worker est mort.

---

## Voir aussi

- [scripts_overview.md](scripts_overview.md) — description complète de chaque script
- [payloads_by_script.md](payloads_by_script.md) — référence des champs de payload
- [sharepoint_structure.md](sharepoint_structure.md) — hiérarchie complète des dossiers SharePoint
- [pipeline_data_manuelle.md](pipeline_data_manuelle.md) — import des données manuelles
- [ddif_architecture.md](ddif_architecture.md) — pipeline DDIF (DBF)
