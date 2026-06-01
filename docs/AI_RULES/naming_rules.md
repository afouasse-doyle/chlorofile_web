# Conventions de nommage

## Fichiers scripts

- Noms de fichiers en **minuscules avec underscores** : `name_builder.py`, `create_kizeo_user_structure.py`
- Jamais de PascalCase ni camelCase pour les fichiers

---

## Modèles Pydantic

- **PascalCase + suffixe `Payload`** : `NameBuilderPayload`, `CreateKizeoUserStructurePayload`
- Un modèle par script dispatcher, défini dans `payload_models.py`

## Type aliases dans `payload_models.py`

- **PascalCase + suffixe `Str`** : `FormIdStr`, `BdStr`, `YearSuffixStr`, `ExportTypeStr`

---

## Fonctions

- **snake_case** pour toutes les fonctions : `handle()`, `fetch_user_ref1()`, `build_names()`
- Préfixe `_` pour les helpers privés : `_build_names()`, `_sanitize_filename()`, `_api_get()`

---

## Constantes et variables module-level

- **UPPER_SNAKE_CASE** pour les constantes : `CURRENT_DIR`, `BASE_DIR`, `OUTPUT_ROOT`
- Logger module-level : `LOG = logging.getLogger("nom_du_script_sans_extension")`

```python
# ✅ — correspond au nom du fichier sans .py
LOG = logging.getLogger("name_builder")
LOG = logging.getLogger("build_ddif_exports")
```

---

## `query_name` dans `exec_sql`

Format : **`<objet_ou_contexte>_<opération>`** en snake_case.

```python
# ✅
exec_sql(conn, "...", params, query_name="kizeo_users_upsert")
exec_sql(conn, "...", params, query_name="export_logs_insert")
exec_sql(conn, "...", params, query_name="user_ref1_fetch")
exec_sql(conn, "...", params, query_name="prescriptions_sync")
exec_sql(conn, "...", params, query_name="parcelles_soft_delete")

# ❌ — trop vague ou format incorrect
exec_sql(conn, "...", params, query_name="select")
exec_sql(conn, "...", params, query_name="mon_script_ma_requete_1")
exec_sql(conn, "...", params, query_name="kizeoUsersFetch")
```

Règles :
- Toujours snake_case
- L'objet = la table ou le contexte métier (pas le nom du script)
- L'opération = ce que fait la requête (`fetch`, `upsert`, `insert`, `update`, `delete`, `soft_delete`, `sync`, `schema`, `index`)

---

## Fonctions SQL DDIF

Format : `app.ddif_<year_suffix>_<traitement>_<region>_<export>`

- Les tirets de `year_suffix` deviennent des underscores
- Tout en minuscules

```sql
-- ✅
app.ddif_2025_2026_degapt_bsl_info_gen
app.ddif_2025_2026_degapt_bsl_dnbr_epc

-- ❌
app.ddif_2025-2026_degapt_bsl_info_gen
app.DDIF_2025_2026_DEGAPT_BSL_INFO_GEN
```

---

## Tables et schémas PostgreSQL

- Noms de tables et schémas en **snake_case minuscules** : `app.kizeo_users`, `app.kizeo_form_exports`
- Schéma par formulaire = `form_id` (chaîne numérique, ex: `"880205"`)
- Schéma transversal = `app`

---

## Variables d'environnement

- **SCREAMING_SNAKE_CASE** obligatoire : `KIZEO_TOKEN`, `PG_HOST`, `SMTP_PASSWORD`
- Préfixe par domaine fonctionnel :

| Domaine | Préfixe | Exemples |
|---|---|---|
| PostgreSQL | `PG_` | `PG_HOST`, `PG_USER`, `PG_PASS` |
| Kizeo | `KIZEO_` | `KIZEO_TOKEN`, `KIZEO_API_URL` |
| Microsoft Graph / SharePoint | `GRAPH_` | `GRAPH_TENANT_ID`, `GRAPH_CLIENT_SECRET` |
| Email / SMTP | `SMTP_` ou `MAIL_` | `SMTP_HOST`, `MAIL_FROM` |
| Flask / dispatcher | nom direct | `HOST`, `PORT`, `LOG_FILE`, `MAX_WORKERS` |
| Chemins locaux | nom descriptif | `BASE_DIR`, `SCRIPTS_DIR`, `OUTPUT_DIR_*` |

- Ne jamais créer une variable sans la documenter dans `docs/env_variables.md`
- Ne jamais inventer un préfixe si un préfixe du domaine existe déjà

---

## Voir aussi

- Conventions d'écriture SQL et usage de `exec_sql` : `docs/AI_RULES/sql_rules.md`
- Structure des scripts et nommage des loggers : `docs/AI_RULES/python_script_standard.md`
