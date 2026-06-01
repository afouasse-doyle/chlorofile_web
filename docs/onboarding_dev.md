# Onboarding Développeur
*Guide pour prendre en main le pipeline Kizeo → Flask → PostgreSQL → SharePoint*

---

# 1. Architecture globale

Le pipeline complet :

```
Kizeo Forms → Make (webhooks) → Flask (dispatcher) → Scripts Python
                                                          ↓         ↓
                                                    PostgreSQL   SharePoint
                                                          ↓
                                                    Clients ODBC (Excel, PowerBI, QGIS)
```

Lire en premier : [architecture.md](architecture.md)

---

# 2. Pré-requis

## 2.1. Outils

- Python **3.11+**
- Git
- PostgreSQL client (psql, DBeaver, pgAdmin)
- VS Code (recommandé)
- Accès RDP au serveur Windows

## 2.2. Accès à recevoir

- Accès au dépôt Git
- Variables d'environnement nécessaires (à obtenir de l'administrateur — workflow à définir)
- Accès PostgreSQL (utilisateur applicatif)
- Token Kizeo

> **1Password** est utilisé uniquement pour la rotation automatique de la clé `X-Auth-Key` (Flask ↔ Make). Ce n'est pas la source des secrets pour le développement local.

> Pas de base de test pour l'instant — tout test se fait sur l'environnement de production avec précaution.

---

# 3. Installer le projet

```bash
git clone <repo>
cd flaskapp
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Le fichier `.env` est stocké **hors du répertoire projet** — il n'existe pas à la racine de `c:\srv\flaskapp\`. En production, NSSM injecte les variables directement dans l'environnement du service.

> **Développement local** : le workflow est à définir — contacter l'administrateur pour obtenir les valeurs nécessaires. Une fois obtenues, créer le fichier dans un dossier externe au dépôt Git et pointer vers lui :
> ```powershell
> $env:ENV_FILE = "C:\chemin\hors\repo\.env"
> ```

Variables minimales à configurer (voir [env_variables.md](env_variables.md) pour la liste complète) :

```ini
PG_HOST=...
PG_PORT=5432
PG_USER=...
PG_PASS=...
PG_DB=...
PG_SSLMODE=require

KIZEO_TOKEN=...

MAKE_AUTH_FILE_PATH=C:\srv\flaskapp\secrets\make_auth.json

GRAPH_TENANT_ID=...
GRAPH_CLIENT_ID=...
GRAPH_CLIENT_SECRET=...
GRAPH_SP_HOST=...
GRAPH_SP_SITE_PATH=...
GRAPH_SHAREPOINT_SITE_ID=...
GRAPH_SHAREPOINT_DRIVE_ID=...
GRAPH_SP_ROOT_DIR=General
```

---

# 4. Serveur Flask

Flask est le dispatcher unique — il charge dynamiquement le script demandé et appelle `handle(payload, logger)`.

Démarrer localement :

```bash
python run_flask_server.py
```

Vérifier :

```bash
curl http://localhost:5000/health
```

> Flask refuse de démarrer si `make_auth.json` est absent ou invalide.

Référence complète des endpoints : [api_endpoints.md](api_endpoints.md)

---

# 5. Déclencher un script manuellement

Pour lancer un script Python sans passer par Make directement, utiliser le formulaire Kizeo **"Lancer script python"** (form_id `1108810`).

| Champ Kizeo | Rôle |
|---|---|
| Opération a effectuer | Type d'opération (liste) |
| Script a lancer | Nom exact du script Python (ex: `create_kizeo_user_structure.py`) |
| BD a mettre à jour ? | Nom de la base PostgreSQL cible |
| ID formulaire a mettre à jour ? | `form_id` si le script en a besoin (sinon vide) |
| ID liste a mettre à jour ? | ID de liste Kizeo si applicable (sinon vide) |

Soumettre le formulaire → déclenche Make → Flask → script.

> C'est le mécanisme standard pour toutes les opérations manuelles : sync catalogue, schema builder, sync utilisateurs, etc.

---

# 6. Règles fondamentales du codebase (CLAUDE.md)

À lire et respecter impérativement — [CLAUDE.md](../CLAUDE.md) :

| Règle | Détail |
|---|---|
| Validation payload | Toujours dans `payload_models.py` — jamais inline |
| SQL | Toujours dans `safe_db.py` — jamais dans un script |
| `user_ref1` | Toujours résolu depuis la BD via `user_id` — jamais depuis la payload |
| Secrets | Toujours dans `.env` — jamais dans le code |
| Modèles Pydantic | `extra="forbid"` par défaut |
| Code mort | `scripts/expires/` — ne pas référencer ni s'en inspirer |

---

# 7. Les pipelines

## 7.1. Ingestion Kizeo → PostgreSQL

Make appelle **un seul script** : `fetch_data_kizeo_api.py`

```
fetch_data_kizeo_api  →  upsert_data_postgresql (interne)
                                    ↓
                         mark_action_kizeo_api (subprocess)
```

Pour un delete Kizeo : même script avec `"deleted": true` dans la payload — le GET API est skippé.

Référence : [pipeline_kizeo.md](pipeline_kizeo.md)

## 7.2. Exports Kizeo → SharePoint (Excel / PDF)

```
name_builder  →  download_kizeo_file  →  SharePoint
                         ↓
               register_kizeo_export  →  build_rapport_execution
                         ↓
               pdf_queue/job.json  →  excel_worker (Desktop session)
```

Référence : [pipeline_exports.md](pipeline_exports.md)

## 7.3. DDIF → SharePoint

```
ddif_name_builder  →  build_ddif_exports (subprocess)  →  SharePoint (*.dbf)
```

Référence : [ddif_architecture.md](ddif_architecture.md)

## 7.4. Data manuelle

Deux flux depuis les mêmes fichiers SharePoint :

```
upsert_data_manuelle_db   →  PostgreSQL (prescriptions, parcelles, secteur_intervention_reb)
create_kizeo_lists_excel  →  create_kizeo_lists_json  →  upload_lists_to_kizeo  →  Kizeo API
```

Référence : [pipeline_data_manuelle.md](pipeline_data_manuelle.md)

---

# 8. Structure SharePoint

100% Microsoft Graph — aucun fichier permanent en local. Structure principale :

```
General/
 └── <coop_directory>/
     └── <year_suffix>/
         └── <form_name>/
             └── [<region>/][<ue>/]
                 ├── fichier.xlsx / .pdf
                 ├── RE_<UE>.xlsx
                 └── ddif/*.dbf
```

Référence : [sharepoint_structure.md](sharepoint_structure.md)

---

# 9. Base PostgreSQL

- **Schémas par `form_id`** : chaque formulaire Kizeo a son propre schéma (ex: `880205`)
- **Schéma `app`** : 13 tables transversales (coops, users, catalog, logs, data manuelle…)
- **RLS** : chaque coop ne voit que ses données via `user_ref1`

Tables clés à connaître : `app.coops`, `app.kizeo_users`, `app.kizeo_form_exports`, `app.kizeo_export_logs`

Référence : [postgresql_schema.md](postgresql_schema.md)

---

# 10. Sécurité & secrets

- Les secrets sont dans `.env` (non versionné) et dans 1Password (`INFRA - PROD`)
- La clé `X-Auth-Key` (Make → Flask) est **rotée quotidiennement** via `rotate_make_to_flask_auth.py` — ne pas la stocker manuellement

Référence : [secrets_rotation.md](secrets_rotation.md) | [security_env.md](security_env.md) | [env_variables.md](env_variables.md)

---

# 11. Ajouter un nouveau script

1. Créer `scripts/<nom_script>.py` avec `handle(payload: dict, logger) -> dict`
2. **Créer le modèle Pydantic** dans `scripts/payload_models.py` avec `extra="forbid"`
3. Si SQL nécessaire : ajouter le helper dans `scripts/safe_db.py`
4. Tester en CLI si possible
5. Déclarer dans Make (`X-Script-Name: nom_script.py`)
6. **Mettre à jour `docs/scripts_overview.md`**

---

# 12. Déployer une modification

1. Commit & push sur GitHub
2. Copier les fichiers modifiés sur le serveur
3. Redémarrer le service Flask (NSSM) :
   ```
   nssm restart flaskapp
   ```
4. Vérifier `/health`
5. Tester un appel Make

---

# 13. Debug

- Logs Flask : `logs/flask.log`
- Logs scripts : `logs/<script>_<timestamp>.log`
- Heartbeat Excel worker : `logs/excel_worker_heartbeat.json`
- SQL : psql / DBeaver / pgAdmin
- HTTP : `curl` ou Postman

Référence : [troubleshooting.md](troubleshooting.md)

---

# 14. Checklist onboarding

- [ ] Accès Git
- [ ] Python 3.11+ installé, `.venv` créé
- [ ] `.env` configuré
- [ ] Accès 1Password (vault `INFRA - PROD`)
- [ ] Accès PostgreSQL fonctionnel
- [ ] Token Kizeo configuré
- [ ] `make_auth.json` présent (ou rotation configurée)
- [ ] Flask démarre et répond sur `/health`
- [ ] Lecture de `architecture.md`, `scripts_overview.md`, `CLAUDE.md`

---

# 15. Voir aussi

- [architecture.md](architecture.md) — vue globale
- [scripts_overview.md](scripts_overview.md) — tous les scripts
- [env_variables.md](env_variables.md) — toutes les variables `.env`
- [api_endpoints.md](api_endpoints.md) — endpoints Flask
- [pipeline_kizeo.md](pipeline_kizeo.md) — ingestion
- [pipeline_exports.md](pipeline_exports.md) — exports Excel/PDF
- [pipeline_data_manuelle.md](pipeline_data_manuelle.md) — data manuelle
- [ddif_architecture.md](ddif_architecture.md) — DDIF
- [sharepoint_structure.md](sharepoint_structure.md) — SharePoint
- [postgresql_schema.md](postgresql_schema.md) — base de données
- [secrets_rotation.md](secrets_rotation.md) — rotation des secrets
- [troubleshooting.md](troubleshooting.md) — debug
- [ajout_nouvelle_coop.md](ajout_nouvelle_coop.md) — procédure d'ajout d'une coop
- [ajout_utilisateur_kizeo.md](ajout_utilisateur_kizeo.md) — procédure après création d'un utilisateur Kizeo
- [ajout_nouveau_formulaire_kizeo.md](ajout_nouveau_formulaire_kizeo.md) — procédure d'ajout d'un formulaire
- [excel_worker.md](excel_worker.md) — worker de conversion Excel → PDF
- [bd_acces_autorisation.md](bd_acces_autorisation.md) — gestion des accès ODBC (DISCOVER → REFRESH → APPLY)
