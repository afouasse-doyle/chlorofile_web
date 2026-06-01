# Standard Python — scripts dispatcher

## Contrat obligatoire

Tout script appelé par le dispatcher Flask expose exactement cette signature :

```python
def handle(payload: dict, logger) -> dict:
```

- `payload` : dict brut reçu via `/run`
- `logger` : logger fourni par le dispatcher — ne jamais le recréer ni le reconfigurer
- retour : dict JSON-sérialisable (jamais `None`, jamais une exception non capturée)

---

## En-tête standard

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nom_du_script.py

Description courte du rôle dans le pipeline.
Étapes principales.
"""

from __future__ import annotations
```

---

## Bloc sys.path — obligatoire, toujours en premier

Doit apparaître **avant tout import local** (`payload_models`, `safe_db`, `graph_storage`, etc.).

```python
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
```

Variante acceptée avec `pathlib` :

```python
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))
```

---

## Ordre des imports

```python
# 1. Stdlib
import os
import sys
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

# 2. Bloc sys.path (si pas encore fait ci-dessus)

# 3. Tiers (requests, pandas, pydantic…)
import requests

# 4. Locaux (après sys.path)
from payload_models import MonScriptPayload
from safe_db import pg_connect, exec_sql
from graph_storage import sp_upload_file
```

---

## Variables d'environnement

Dans `handle()` : utiliser uniquement `os.getenv(...)`.

```python
# ✅
token = os.getenv("KIZEO_TOKEN")

# ❌ — jamais dans handle() ou à la racine du module
load_dotenv()
```

Le chargement du `.env` est géré par `safe_db.py` (via `CHLOROFILE_ENV_PATH`) et par le dispatcher Flask. Les scripts n'y touchent pas.

Exception : le bloc `if __name__ == "__main__":` doit charger le `.env` externe via `CHLOROFILE_ENV_PATH` :

```python
if __name__ == "__main__":
    from dotenv import load_dotenv
    _ep = os.environ.get("CHLOROFILE_ENV_PATH")
    if not _ep:
        raise SystemExit("CHLOROFILE_ENV_PATH non définie")
    load_dotenv(_ep)
```

### Utiliser ou créer une variable d'environnement

**Avant d'utiliser ou créer une variable :**

1. Lire `docs/env_variables.md` — la variable existe peut-être déjà sous un nom légèrement différent
2. Ne jamais dupliquer une variable existante (ex : `PG_HOST` et `PGHOST` coexistent déjà — ne pas en créer une troisième)

**Si la variable n'existe pas et doit être créée :**

1. L'ajouter dans le fichier `.env` externe
2. La documenter dans `docs/env_variables.md` avec son statut (`R` requis / `O` optionnel) et sa description
3. Respecter les conventions de nommage → `docs/AI_RULES/naming_rules.md`

---

## Contrat de retour de `handle()`

`handle()` retourne **toujours un dict** — jamais `None`, jamais une exception non capturée.

Le dispatcher Flask est asynchrone : il retourne un HTTP 202 à Make immédiatement, puis exécute le script dans un thread. Make ne voit jamais le résultat de `handle()`. Les erreurs doivent donc être gérées et loggées en interne.

**Pattern obligatoire — catch global en fin de `handle()` :**

```python
def handle(payload: dict, logger) -> dict:
    try:
        # ... tout le code ...

        return {"status": "ok", ...}

    except Exception as e:
        logger.exception("FAILED mon_script")
        return {"status": "error", "step": "...", "error": str(e)}
```

- Le catch global **ne re-raise jamais** — il retourne un dict `{"status": "error"}`
- `raise` est autorisé dans les blocs intermédiaires pour remonter jusqu'au catch global
- Le dispatcher lit `status` dans le dict retourné pour loguer `END status=ok` ou `END status=error`

> **Note legacy :** certains scripts existants font `raise` dans le catch global. C'est non conforme — à corriger progressivement.

---

## Validation Pydantic — premier appel dans `handle()`

```python
from payload_models import MonScriptPayload

def handle(payload: dict, logger) -> dict:
    data = MonScriptPayload(**payload)
    # À partir d'ici, utiliser data.<champ> uniquement
```

- Toujours en tout premier, avant toute logique métier
- Le modèle est dans `payload_models.py` — jamais inline dans le script
- `extra="forbid"` par défaut sur tous les modèles
- `user_ref1` ne vient **jamais** de la payload — toujours résolu depuis la BD via `user_id`

---

## Accès PostgreSQL

```python
from safe_db import pg_connect, exec_sql

conn = pg_connect(dbname=data.bd)
rows = exec_sql(conn, "SELECT ...", (param,), fetch="all", query_name="mon_script_select")
```

- `psycopg2.connect()` direct : **interdit**
- SQL avec f-string : **interdit**
- SQL inline dans le script : **interdit** — tout passe par `safe_db.py`
- Vérifier si `safe_db.py` a déjà le helper avant d'en créer un nouveau

---

## Bloc `__main__` — tests locaux uniquement

```python
if __name__ == "__main__":
    from dotenv import load_dotenv
    _ep = os.environ.get("CHLOROFILE_ENV_PATH")
    if not _ep:
        raise SystemExit("CHLOROFILE_ENV_PATH non définie")
    load_dotenv(_ep)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    log = logging.getLogger("mon_script")

    test_payload = {
        "form_id": "880205",
        "bd": "chlorofile2",
        # ...
    }

    result = handle(test_payload, log)
    print(json.dumps(result, ensure_ascii=False, indent=2))
```

- `logging.basicConfig` : **uniquement ici**, jamais à la racine du module ni dans `handle()`
- `print()` : autorisé uniquement ici pour afficher le résultat
- `print()` pour le logging applicatif : **interdit partout**

Exception — scripts appelés **exclusivement en subprocess** (ex : `build_ddif_exports.py`) :
- `print()` est autorisé pour produire une sortie JSON structurée attendue par le script appelant
- `logging.basicConfig` peut être présent au niveau module (le script n'est pas chargé par le dispatcher Flask)

---

## Chemins de sous-scripts — toujours relatifs

```python
# ✅
script_path = Path(__file__).parent / "upsert_data_postgresql.py"

# ❌
script_path = "C:/srv/flaskapp/scripts/upsert_data_postgresql.py"
```

---

## Nom de fichier depuis l'API Kizeo

Le nom de fichier effectif d'un export Kizeo provient **toujours** du header HTTP `Content-Disposition` — jamais reconstruit manuellement depuis les données de la payload ou de la BD.

---

## Interdictions absolues

| Interdit | Raison |
|---|---|
| `psycopg2.connect()` direct | Tout passe par `safe_db.pg_connect()` |
| SQL avec f-string | Risque d'injection SQL |
| SQL inline dans un script | Tout le SQL appartient à `safe_db.py` |
| `print()` pour logging | Utiliser le `logger` fourni |
| `logging.basicConfig()` hors `__main__` | Interfère avec le dispatcher |
| `load_dotenv()` dans `handle()` | Géré par `safe_db.py` et le dispatcher |
| Secrets dans le code | Tout est dans `.env` via `CHLOROFILE_ENV_PATH` |
| Chemin subprocess hardcodé | Utiliser `Path(__file__).parent` |
| `user_ref1` depuis la payload | Toujours résolu depuis la BD via `user_id` |

---

## Voir aussi

- Règles de logging dans les scripts : `docs/AI_RULES/logging_rules.md`
- Sécurité payload et SQL : `docs/AI_RULES/security_rules.md`
- Conventions d'écriture SQL et `exec_sql` : `docs/AI_RULES/sql_rules.md`
- Conventions de nommage (fichiers, fonctions, variables env, tables) : `docs/AI_RULES/naming_rules.md`

## Template complet

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mon_script.py

Description du rôle dans le pipeline.
"""

from __future__ import annotations

import os
import sys
import json
import logging
from pathlib import Path
from typing import Any, Dict

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from payload_models import MonScriptPayload
from safe_db import pg_connect, exec_sql


def handle(payload: Dict[str, Any], logger) -> Dict[str, Any]:
    data = MonScriptPayload(**payload)

    logger.info("START mon_script bd=%s", data.bd)

    try:
        conn = pg_connect(data.bd)
        rows = exec_sql(conn, "SELECT ...", (data.form_id,), fetch="all", query_name="mon_script_select")
        logger.info("PG OK rows=%d", len(rows))
    except Exception:
        logger.exception("PG failed")
        raise

    logger.info("DONE ✔ rows=%d", len(rows))
    return {"status": "ok", "rows": len(rows), "bd": data.bd}


if __name__ == "__main__":
    from dotenv import load_dotenv
    _ep = os.environ.get("CHLOROFILE_ENV_PATH")
    if not _ep:
        raise SystemExit("CHLOROFILE_ENV_PATH non définie")
    load_dotenv(_ep)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    log = logging.getLogger("mon_script")

    result = handle({"form_id": "880205", "bd": "chlorofile2"}, log)
    print(json.dumps(result, ensure_ascii=False, indent=2))
```
