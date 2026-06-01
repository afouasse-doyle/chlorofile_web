# Règles de sécurité

## 1. Validation des payloads

Tout script dispatcher valide sa payload **en premier**, avant toute logique métier, via un modèle Pydantic dédié dans `payload_models.py`.

```python
from payload_models import NameBuilderPayload

def handle(payload: dict, logger) -> dict:
    data = NameBuilderPayload(**payload)
    # À partir d'ici, utiliser data.<champ> uniquement
```

**Règles des modèles :**

- `extra = "forbid"` sur tous les modèles — toute clé inconnue fait échouer immédiatement.
- Types stricts avec patterns regex :

| Type alias | Pattern | Usage |
|---|---|---|
| `FormIdStr` | `^\d+$` | form_id, data_id, user_id |
| `BdStr` | `^[A-Za-z0-9_\-]+$` | nom de base PostgreSQL |
| `YearSuffixStr` | `^\d{4}-\d{4}$` | year_suffix |
| `ExportTypeStr` | `^(excel\|pdf)$` | export_type |
| `ActionStr` | `^[A-Za-z0-9_\-]+$` | action Kizeo |

- Normalisation automatique : trim des espaces, conversion `int → str` pour les IDs.
- `payload_models.py` = **input only** — aucun champ calculé ou enrichi.

---

## 2. Sécurité SQL

### Requêtes paramétrées uniquement

```python
# ✅
rows = exec_sql(
    conn,
    "SELECT export_id FROM app.kizeo_form_exports WHERE form_id = %s",
    (str(form_id),),
    fetch="one",
    query_name="fetch_export_id",
)

# ❌ — injection SQL possible
query = f"SELECT * FROM app.exports WHERE form_id = '{form_id}'"
```

### Identifiants dynamiques — `psycopg2.sql`

Pour les noms de tables ou de colonnes dynamiques, utiliser `psycopg2.sql` :

```python
from psycopg2 import sql

q = sql.SQL("SELECT 1 FROM {}.{}").format(
    sql.Identifier(schema),
    sql.Identifier(table),
)
```

### Interdictions absolues

- `psycopg2.connect()` direct dans un script : **interdit** — utiliser `safe_db.pg_connect()`
- SQL construit avec f-string : **interdit**
- SQL inline dans un script : **interdit** — tout le SQL appartient à `safe_db.py`

`safe_db.pg_connect()` valide le nom de base avec `^[A-Za-z0-9_\-]+$` avant toute connexion.

---

## 3. RLS — Row Level Security

La colonne `user_ref1` est la clé de sécurité RLS. Elle identifie la coop d'un enregistrement.

**Règle absolue : `user_ref1` ne vient jamais de la payload.**

```python
# ✅ — résolu depuis la BD via user_id
user_ref1 = fetch_user_ref1(conn, data.user_id)

# ❌ — ne jamais faire confiance à ce champ s'il vient de la payload entrante
user_ref1 = payload.get("user_ref1")
```

- `user_ref1` provient toujours de `app.kizeo_users` (via `fetch_user_ref1`) ou du DataFrame (data manuelle).
- Ne jamais bypasser ou désactiver la RLS dans un script (`SET ROLE`, `ALTER POLICY` : interdits).
- Les rôles ODBC (ex : `abifor_odbc`) sont en lecture seule avec RLS active.

---

## 4. Secrets

### Règle absolue : aucun secret dans le code

- Pas de token, mot de passe, clé API hardcodés dans les scripts.
- Tout est dans le fichier `.env` externe, chargé via `CHLOROFILE_ENV_PATH`.
- Le `.env` est stocké **hors du répertoire projet** et hors du dépôt Git.

### Accès aux secrets dans les scripts

```python
# ✅ — dans handle(), via os.getenv
token = os.getenv("KIZEO_TOKEN")

# ✅ — dans __main__ uniquement, via CHLOROFILE_ENV_PATH
if __name__ == "__main__":
    from dotenv import load_dotenv
    _ep = os.environ.get("CHLOROFILE_ENV_PATH")
    if not _ep:
        raise SystemExit("CHLOROFILE_ENV_PATH non définie")
    load_dotenv(_ep)
```

Le chargement du `.env` en production est géré par `safe_db.py` (via `CHLOROFILE_ENV_PATH`) et le dispatcher Flask — jamais par les scripts eux-mêmes.

### Authentification Flask (X-Auth-Key)

Flask valide chaque requête via un système **dual-key** :
- clé courante + clé précédente avec fenêtre de grâce de 30 minutes.
- Géré par `rotate_make_to_flask_auth.py` (rotation quotidienne via 1Password).
- La clé n'est pas dans `.env` — elle est dans `make_auth.json`, lu par Flask.

---

## 5. Secrets dans les logs

Ne jamais logger :
- Tokens (KIZEO_TOKEN, GRAPH_CLIENT_SECRET, etc.)
- Mots de passe
- Payloads complètes si elles contiennent des champs sensibles

En cas d'erreur de validation, redacter les champs sensibles avant de logger :

```python
safe_payload = {
    k: ("<redacted>" if any(s in str(k).lower() for s in ("token", "secret", "pass", "password", "key")) else v)
    for k, v in (payload or {}).items()
}
logger.error("Payload invalide: errors=%s payload=%s", e.errors(), safe_payload)
```

---

## Voir aussi

- Conventions d'écriture SQL, DDL idempotent, transactions : `docs/AI_RULES/sql_rules.md`
- Variables d'environnement et gestion des secrets : `docs/security_env.md`
```
