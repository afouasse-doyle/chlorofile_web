# Règles SQL

> **Note :** les règles SQL sont réparties sur plusieurs fichiers selon le contexte :
> - **Sécurité SQL** (injection, requêtes paramétrées, RLS) → `docs/AI_RULES/security_rules.md`
> - **SQL DDIF** (signature des fonctions, filtrage STRICT, ORDER BY) → `docs/AI_RULES/ddif_rules.md`
> - **Nommage** (tables, schémas, `query_name`) → `docs/AI_RULES/naming_rules.md`
> - **Ce fichier** : conventions générales d'écriture SQL dans le projet

---

## Tout le SQL passe par `safe_db.py`

Aucun SQL brut dans les scripts métier. Toute requête passe par `exec_sql()` ou un helper dédié de `safe_db.py`.

Vérifier si `safe_db.py` a déjà un helper avant d'en créer un nouveau.

---

## `exec_sql` — paramètre `fetch`

| Valeur | Quand l'utiliser |
|---|---|
| `fetch=None` | INSERT, UPDATE, DELETE, DDL — pas de résultat attendu |
| `fetch="one"` | SELECT qui retourne au plus une ligne |
| `fetch="all"` | SELECT qui retourne plusieurs lignes |

```python
# ✅
exec_sql(conn, "INSERT INTO ...", params, fetch=None, query_name="...")
exec_sql(conn, "SELECT ... LIMIT 1", params, fetch="one", query_name="...")
exec_sql(conn, "SELECT ...", params, fetch="all", query_name="...")
```

---

## DDL — structure obligatoire d'une table

Toute nouvelle table dans `safe_db.py` doit avoir une colonne **`id BIGSERIAL`** — elle permet d'ordonner les lignes par ordre d'insertion (`ORDER BY id ASC`) indépendamment des timestamps.

Elle peut être la PK ou non selon le contexte :

```sql
-- ✅ id = PK (table sans clé métier naturelle)
CREATE TABLE IF NOT EXISTS app.ma_table (
    id          BIGSERIAL PRIMARY KEY,
    ...
);

-- ✅ id = tri seulement, PK métier séparée
CREATE TABLE IF NOT EXISTS app.ma_table (
    id          BIGSERIAL,
    run_id      UUID PRIMARY KEY,
    ...
);
```

Pour les tables existantes sans `id`, ajouter la migration dans `ensure_*` :

```python
exec_sql(conn,
    "ALTER TABLE app.ma_table ADD COLUMN IF NOT EXISTS id BIGSERIAL;",
    query_name="ma_table_add_id_bigserial",
)
```

---

## DDL — toujours idempotent

Toutes les opérations DDL doivent être rejouables sans erreur.

```sql
-- ✅
CREATE SCHEMA IF NOT EXISTS app;
CREATE TABLE IF NOT EXISTS app.ma_table (...);
ALTER TABLE app.ma_table ADD COLUMN IF NOT EXISTS ma_colonne TEXT;
CREATE INDEX IF NOT EXISTS mon_index ON app.ma_table (ma_colonne);

-- ❌
CREATE TABLE app.ma_table (...);  -- plante si déjà existante
ALTER TABLE app.ma_table ADD COLUMN ma_colonne TEXT;  -- plante si déjà existante
```

Les fonctions `ensure_*` dans `safe_db.py` encapsulent ce pattern — les utiliser plutôt que réécrire le DDL dans les scripts.

---

## Transactions

`exec_sql()` fait un `commit` automatique après chaque requête.

Pour les opérations bulk (plusieurs requêtes liées), utiliser un curseur direct avec `conn.commit()` explicite en fin de bloc :

```python
with conn.cursor() as cur:
    cur.execute("INSERT INTO ...", params1)
    cur.execute("UPDATE ...", params2)
conn.commit()
```

En cas d'erreur, `exec_sql` fait un `rollback` automatique. Pour les curseurs directs, gérer le rollback explicitement :

```python
try:
    with conn.cursor() as cur:
        cur.execute(...)
    conn.commit()
except Exception:
    conn.rollback()
    raise
```

---

## `psycopg2.sql` — identifiants dynamiques uniquement

`psycopg2.sql` est réservé aux **noms de tables, schémas et colonnes** dynamiques — jamais pour les valeurs.

```python
from psycopg2 import sql

# ✅ — identifiant dynamique
q = sql.SQL("SELECT 1 FROM {}.{}").format(
    sql.Identifier(schema),
    sql.Identifier(table),
)

# ✅ — valeur dynamique → paramètre %s
exec_sql(conn, "SELECT * FROM app.ma_table WHERE id = %s", (some_id,))

# ❌ — ne jamais utiliser sql.Literal pour contourner les paramètres
```

---

## Requêtes longues — lisibilité

Pour les requêtes complexes, définir la SQL comme constante de module (pattern de `safe_db.py`) :

```python
_SQL_FETCH_EXPORT = """
SELECT export_id::text, name_excel, form_name
FROM app.kizeo_form_exports
WHERE form_id::text = %s::text
  AND name_excel ILIKE %s
ORDER BY updated_at DESC NULLS LAST
LIMIT 1
"""

rows = exec_sql(conn, _SQL_FETCH_EXPORT, (form_id, export_name), fetch="one", query_name="export_id_fetch")
```

---

## Organisation interne de `safe_db.py`

Le fichier est structuré en **sections nommées**. Chaque section couvre un périmètre fonctionnel distinct et est associée à un ou plusieurs scripts consommateurs.

### Format de bannière de section

```python
# ====================================================================
# SECTION : <nom descriptif>
# Scripts : <script_1.py>, <script_2.py>          (ou "tous les scripts")
# Tables  : <app.table_1>, <app.table_2>           (ou "—" si aucune)
# ====================================================================
```

### Sections officielles (ordre du fichier)

| # | Nom de section | Scripts consommateurs | Tables principales |
|---|---|---|---|
| 1 | Infrastructure | tous les scripts | — |
| 2 | Lookups partagés | `name_builder.py`, `ddif_name_builder.py`, `register_kizeo_export.py` | `app.kizeo_form_exports`, `app.kizeo_users`, `app.coops` |
| 3 | Kizeo users | `create_kizeo_user_structure.py` | `app.kizeo_users` |
| 4 | Kizeo export logs | `register_kizeo_export.py` | `app.kizeo_export_logs` |
| 5 | Data manuelle | `upsert_data_manuelle_db.py` | `app.prescriptions`, `app.secteur_intervention_reb`, `app.parcelles`, `app.data_manuelle_files` |
| 6 | Catalogue Kizeo | `sync_kizeo_catalog.py` | `app.kizeo_forms`, `app.kizeo_lists`, `app.kizeo_form_fields`, `app.kizeo_form_exports`, `app.kizeo_form_lists` |

**Section 1 — Infrastructure** : `_norm_pk`, `LOG`, `_ensure_env_loaded`, `pg_connect`, `exec_sql`. Aucun SQL métier ici.

**Section 2 — Lookups partagés** : fonctions de lecture simples utilisées par plusieurs scripts. Si une nouvelle fonction est nécessaire pour un seul script, elle va dans la section de ce script. Si elle est partagée entre 2+ scripts, elle vient ici.

### Règles de placement

1. **Nouvelle fonction pour un seul script** → section de ce script (par nom de section).
2. **Nouvelle fonction partagée entre 2+ scripts** → section "Lookups partagés", avec la liste complète des scripts dans la ligne `# Scripts :`.
3. **Nouvelle section requise** (nouveau script ou nouveau domaine fonctionnel) → créer la bannière complète avec `Scripts :` et `Tables :`, l'ajouter au tableau ci-dessus.
4. **Ne jamais intercaler** des fonctions d'une section dans une autre.
5. **Pas de curseur brut** dans `safe_db.py` — toujours passer par `exec_sql(conn, query, params, fetch=..., query_name=...)` pour garantir le logging et le rollback automatique.
