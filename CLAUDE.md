# CLAUDE.md — Chlorofile 2.0

## Architecture

Flux principal : Kizeo → Make (webhooks) → Flask (`run_flask_server.py`) → `scripts/` → PostgreSQL → Clients ODBC / SharePoint / Exports

* Make appelle Flask via `POST /run` avec les headers `X-Script-Name` et `X-Auth-Key`
* Flask charge dynamiquement le script demandé et appelle `handle(payload, logger)`
* Chaque script a une responsabilité unique et suit ce contrat obligatoire :

  ```python
  def handle(payload: dict, logger) -> dict:
  ```

### Principes fondamentaux

* Flask = dispatcher uniquement
* Python = orchestration uniquement
* PostgreSQL = logique métier
* SharePoint via Microsoft Graph uniquement
* Sécurité par RLS (`user_ref1`)
* Architecture DDIF pack-driven (`year_suffix / formulaire / region`)

---

## Fichiers clés

| Fichier                     | Rôle                                                 |
| --------------------------- | ---------------------------------------------------- |
| `scripts/safe_db.py`        | Couche DB centralisée — tout le SQL passe par ici    |
| `scripts/payload_models.py` | Contrats Pydantic pour toutes les payloads entrantes |
| `run_flask_server.py`       | Dispatcher Flask — lecture seule                     |
| `docs/postgresql_schema.md` | Référence schéma PostgreSQL                          |
| `docs/scripts_overview.md`  | À mettre à jour quand on ajoute un script            |

---

## Règles de code critiques

### Ces règles cassent le système si ignorées

* Toute validation de payload → `payload_models.py` uniquement, jamais inline
* Tout SQL → `safe_db.py` uniquement, jamais de SQL brut dans un script
* Jamais de secrets dans le code — tout est dans `.env`, externalisé hors dépôt
* `user_ref1` vient toujours du DataFrame ou de la BD, jamais de la payload entrante (clé RLS)
* Modèles Pydantic avec `extra="forbid"` par défaut
* SQL construit avec f-string : interdit
* `psycopg2.connect()` direct : interdit
* `print()` pour logging : interdit

### Conventions

* Un script = une responsabilité
* `scripts/expires/` = code mort — ne jamais référencer ni s'en inspirer
* La logique métier complexe appartient au SQL PostgreSQL, pas à Python
* Préserver commentaires, indentation et structure lors des patchs
* Éviter les refactors globaux non demandés

---

## Logging

* **Succès** → une ligne compacte : `DONE ✔ ok=7 uploaded=7 error=0`
* **Erreur** → stacktrace complète + contexte + payload résumé
* **Ne jamais logger** : payloads complets, secrets, tokens, credentials, gros JSON inutiles

### Fichiers de log (troubleshooting)

| Fichier                          | Contenu                                      |
| -------------------------------- | -------------------------------------------- |
| `logs/script_data.log`           | Log principal — tous les niveaux INFO+       |
| `logs/errors.log`                | Erreurs uniquement — ERROR+                  |
| `logs/flask_stdout.log`          | Stdout du processus Flask                    |
| `logs/flask_stderr.log`          | Stderr du processus Flask                    |
| `logs/excel_worker.log`          | Worker Excel (monitor)                       |
| `logs/rotate_make_to_flask_auth.log` | Rotation des clés Make→Flask            |
| `logs/caddy-access.log`          | Accès HTTP (reverse proxy Caddy)             |


---

## Comportement automatique attendu

Voir `docs/AI_RULES/collaboration_rules.md` pour les règles complètes.

---

## Ce qu'il ne faut jamais proposer

> Avant de proposer une amélioration sur le pipeline data manuelle ou listes Kizeo, lire `docs/vision.md` — ces scripts sont en sursis.



* Écrire du SQL directement dans un script
* Contourner `payload_models.py` ou `safe_db.py`
* Modifier des fichiers `.py` sans demande explicite
* Exécuter quoi que ce soit sans que ce soit demandé
* `git commit` ou `git push` (bloqués dans les permissions)
* Proposer des tests sur une base de test (`bd=test`) — elle n'existe pas encore

---

## Référence contextuelle

Lire selon le contexte actif :

| Contexte              | Fichier                                                 |
| --------------------- | ------------------------------------------------------- |
| Vision / roadmap      | `docs/vision.md`                                        |
| Architecture générale | `docs/architecture.md`, `docs/scripts_overview.md`      |
| Payloads              | `docs/payloads_by_script.md`                            |
| Schéma PostgreSQL     | `docs/postgresql_schema.md`                             |
| Variables d'env       | `docs/env_variables.md`                                 |
| Logging               | `docs/AI_RULES/logging_rules.md`                        |
| Standards Python      | `docs/AI_RULES/python_script_standard.md`               |
| Sécurité / RLS        | `docs/AI_RULES/security_rules.md`                       |
| Exports DDIF          | `docs/AI_RULES/ddif_rules.md`                           |
| Patching              | `docs/AI_RULES/patching_rules.md`                       |
| Collaboration         | `docs/AI_RULES/collaboration_rules.md`                  |
| Graph / SharePoint    | `docs/AI_RULES/graph_sharepoint_rules.md`               |
| Nommage               | `docs/AI_RULES/naming_rules.md`                         |
| SQL                   | `docs/AI_RULES/sql_rules.md`                            |

**Priorité documentaire :** `CLAUDE.md` > `docs/AI_RULES/*` > `docs/*` > `README.md`

---

## Permissions actives (`settings.local.json`)

| Action                                             | Statut                   |
| -------------------------------------------------- | ------------------------ |
| Lire fichiers `.py`                                | ✅                        |
| Modifier fichiers `.py`                            | ❌ sans demande explicite |
| Modifier `docs/*.md`, `README.md`                  | ✅                        |
| Modifier fichiers `.json`                          | ✅                        |
| `git status`, `git log`, `git diff`, `git restore` | ✅                        |
| `git commit`, `git push`                           | ❌ bloqués                |
