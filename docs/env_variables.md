# Variables d'environnement

Référence complète des variables du fichier `.env`. Ce fichier n'est jamais versionné dans Git.

---

## ⚠️ Variables système Windows obligatoires

Ces 3 variables doivent être définies **de manière permanente dans Windows** (Variables d'environnement système → `[System.Environment]::SetEnvironmentVariable(..., "Machine")`), et non dans le `.env` :

| Variable | Rôle |
|---|---|
| `CHLOROFILE_ENV_PATH` | Chemin vers le fichier `.env` — chargé par Flask avant tout |
| `MAKE_AUTH_FILE_PATH` | Chemin vers `make_auth.json` — lu par Flask et le script de rotation |
| `OP_SERVICE_ACCOUNT_TOKEN` | Token Service Account 1Password — lu par le script de rotation |

---

**Légende** : R = requis, O = optionnel, L = legacy (plus utilisé)

---

## PostgreSQL

| Variable | Statut | Description |
|---|---|---|
| `PG_HOST` | R | Hôte du serveur PostgreSQL |
| `PG_PORT` | R | Port (généralement `5432`) |
| `PG_DB` | R | Nom de la base de données |
| `PG_USER` | R | Utilisateur applicatif |
| `PG_PASS` | R | Mot de passe de l'utilisateur applicatif |
| `PG_SSLMODE` | O | Mode SSL (ex: `require`) |
| `PG_SCHEMA_USER` | O | Schéma cible pour `create_kizeo_user_structure.py` |
| `PG_TABLE_USER` | O | Table cible pour `create_kizeo_user_structure.py` |

---

## Kizeo

| Variable | Statut | Description |
|---|---|---|
| `KIZEO_TOKEN` | R | Token API Kizeo (bearer) |
| `KIZEO_API_URL` | O | URL de base de l'API Kizeo (défaut: `https://www.kizeoforms.com`) |

---

## Flask / Dispatcher

| Variable | Statut | Description |
|---|---|---|
| `MAKE_AUTH_FILE_PATH` | R | Chemin vers `make_auth.json` (dual-key auth — voir [secrets_rotation.md](secrets_rotation.md)) |
| `HOST` | O | Adresse d'écoute Flask (défaut: `0.0.0.0`) |
| `PORT` | O | Port Flask (défaut: `5000`) |
| `MAX_WORKERS` | O | Nombre de workers Flask |
| `DEBUG` | O | Mode debug Flask (`true`/`false`) |
| `LOCK_SCOPE` | O | Scope de verrouillage des scripts |
| `PYTHONUNBUFFERED` | O | Désactiver le buffering Python (recommandé: `1`) |
| `LOG_FILE` | O | Chemin du fichier de log principal (tous niveaux INFO+) |
| `ERRORS_LOG_FILE` | O | Chemin du fichier de log erreurs uniquement (ERROR+) |
| `AUTH_ENV_KEY` | L | Ancien mécanisme d'auth — **non utilisé par Flask** |
| `X_AUTH_KEY` | L | Idem — **non utilisé par Flask** |

> Flask ne lit **jamais** `AUTH_ENV_KEY` ni `X_AUTH_KEY` pour l'authentification. La clé `X-Auth-Key` est gérée exclusivement via `make_auth.json`.

---

## 1Password (rotation)

| Variable | Statut | Description |
|---|---|---|
| `OP_SERVICE_ACCOUNT_TOKEN_ROTATION` | O | Token Service Account 1Password — fallback si absent de Windows Credential Manager |

> En production, ce token est stocké dans Windows Credential Manager (target `OP_SERVICE_ACCOUNT_TOKEN_ROTATION`). La variable `.env` sert de fallback pour les tests manuels.

---

## Email (Excel Worker Monitor)

| Variable | Statut | Description |
|---|---|---|
| `SMTP_HOST` | O | Serveur SMTP pour alertes |
| `SMTP_PORT` | O | Port SMTP |
| `SMTP_USERNAME` | O | Utilisateur SMTP |
| `SMTP_PASSWORD` | O | Mot de passe SMTP |
| `SMTP_USE_TLS` | O | Activer TLS (`true`/`false`) |
| `MAIL_FROM` | O | Adresse expéditeur des alertes |
| `MAIL_TO` | O | Adresse destinataire des alertes |

---

## Microsoft Graph / SharePoint

| Variable | Statut | Description |
|---|---|---|
| `GRAPH_TENANT_ID` | R | ID du tenant Azure AD |
| `GRAPH_CLIENT_ID` | R | ID de l'application (App Registration) |
| `GRAPH_CLIENT_SECRET` | R | Secret de l'application |
| `GRAPH_SP_HOST` | R | Hôte SharePoint (ex: `fqcf.sharepoint.com`) |
| `GRAPH_SP_SITE_PATH` | R | Chemin du site SharePoint |
| `GRAPH_SHAREPOINT_SITE_ID` | R | ID du site SharePoint |
| `GRAPH_SHAREPOINT_DRIVE_ID` | R | ID du drive SharePoint (Document Library) |
| `GRAPH_SP_ROOT_DIR` | O | Dossier racine relatif (défaut: `General`) |
| `GRAPH_PRIMARY_DOMAIN` | O | Domaine principal Azure AD |
| `GRAPH_ONEDRIVE_USER` | O | Utilisateur OneDrive (accès user-based) |
| `ONEDRIVE_ROOT` | L | Ancien chemin OneDrive local — **à supprimer** |

---

## Chemins locaux

| Variable | Statut | Description |
|---|---|---|
| `BASE_DIR` | O | Répertoire de base de l'application |
| `SCRIPTS_DIR` | O | Répertoire des scripts |
| `OUTPUT_DIR_CREATE_KIZEO_USER_STRUCTURE` | O | Dossier de sortie pour `create_kizeo_user_structure.py` |
| `OUTPUT_CREATE_KIZEO_LISTS_EXCEL` | O | Dossier de sortie pour les Excel de listes Kizeo |
| `UPLOAD_KIZEO_JSON_DIR` | O | Dossier des JSON à uploader vers Kizeo |
| `KIZEO_BACKUP_DIR` | O | Dossier de backup des données Kizeo |
| `KIZEO_CATALOG_DETAILS_DIR` | O | Dossier de détails du catalogue Kizeo |
| `output_folder_refresh_kizeo_form_data` | L | Ancien dossier de refresh — à vérifier |
| `OUTPUT_FOLDER_CREATE_POSTGRESQL` | L | Ancien dossier de création PG — à vérifier |
| `CREATE_POSTGRESQL` | L | Ancienne variable de création PG — à vérifier |

---

## Voir aussi

- [secrets_rotation.md](secrets_rotation.md) — architecture de rotation de la clé `X-Auth-Key`
- [security_env.md](security_env.md) — bonnes pratiques de sécurité
- [architecture.md](architecture.md) — vue globale du système
- [AI_RULES/naming_rules.md](AI_RULES/naming_rules.md) — conventions de nommage des variables d'environnement
- [AI_RULES/python_script_standard.md](AI_RULES/python_script_standard.md) — règles d'utilisation et création de variables dans les scripts
