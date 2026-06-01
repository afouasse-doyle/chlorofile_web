# Règles DDIF

> Référence complète : `docs/ddif_architecture.md`

## Principe fondamental

| Élément | Rôle |
|---|---|
| Template DBF | Source de vérité des colonnes (ordre + types) |
| SQL (par export) | Produit les valeurs finales |
| Python | Orchestre, copie, écrit, upload — aucune logique métier |
| Pack régional | Définit les règles (SQL + config) par année/formulaire/région |
| `config.yaml` | Seule source de vérité pour les overrides runtime |

---

## Interdictions absolues

- Aucune logique métier en Python — tout appartient au SQL
- Aucun `form_id` hardcodé — toujours résolution dynamique
- Aucun code spécifique à une région en Python
- Aucune manipulation Excel COM
- Aucune conversion `.XLS → .XLSX`
- Ne jamais modifier un template DBF — on copie puis on écrit dans la copie
- Ne jamais déduire les colonnes finales depuis le SQL — le template décide

---

## `form_name` — exact depuis la BD

`form_name` est récupéré via `fetch_form_name_for_form_id()` et conservé **exactement** tel quel — aucune sanitization, aucune modification.

```python
# ✅
form_name_db = fetch_form_name_for_form_id(conn, form_id)
# form_name utilisé tel quel dans le chemin du pack
```

Exception : refus si le `form_name` contient des caractères interdits Windows (`/`, `\`, `<`, `>`, `:`, `"`, `|`, `?`, `*`) ou s'il se termine par un espace ou un point.

---

## Filtrage SQL STRICT

Toutes les fonctions SQL doivent filtrer strictement par les trois paramètres :

```sql
WHERE t.unite_d_echantillonnage_ue = p_ue
  AND t.region = p_region
  AND t.user_ref1 = (p_cfg->>'user_ref1')
```

- `user_ref1` est **obligatoire** — si NULL ou vide, la fonction doit lever une erreur
- Aucun OR permissif (`cfg.user_ref1 IS NULL OR ...`) : interdit
- Aucune requête cross-coop

---

## Signature SQL standardisée

Toutes les fonctions du pack respectent cette signature :

```sql
CREATE OR REPLACE FUNCTION app.ddif_<year_suffix>_<traitement>_<region>_<export>(
    p_year_suffix text,
    p_region      text,
    p_ue          text,
    p_cfg         jsonb,
    p_form_id     text
)
```

Exemple de nom : `app.ddif_2025_2026_degapt_bsl_dnbr_epc`

---

## Résolution dynamique des tables

`form_id` n'est jamais hardcodé. Toujours utiliser `format()` avec `%I` :

```sql
-- ✅
v_sql := format(
    'SELECT ... FROM %I.%I t WHERE ...',
    p_form_id,
    p_form_id
);

-- ❌
FROM "1052897"."1052897"
```

La table parent = `p_form_id.p_form_id`. Les sous-tables = `p_form_id || '_suffix'`.

---

## `cfg` et `config.yaml`

- Toute valeur overridable depuis la payload **doit** être déclarée dans `cfg_from_payload`
- La SQL lit uniquement `p_cfg->>'clé'` — jamais directement depuis la payload
- `user_ref1` et `id_projet` doivent être déclarés dans `cfg_from_payload` de chaque export qui les supporte
- Aucun fallback implicite — si une clé n'est pas dans `cfg`, elle n'existe pas

---

## `output_dir`

- Chemin **relatif** sous `GRAPH_SP_ROOT_DIR` (`General/`)
- Ne commence **jamais** par `General\`
- Format : `<coop_code>/<year_suffix>/<form_name>/<region>/[<ue>/]`

```python
# ✅ output_dir = "RBT\\2025-2026\\...\\BSL\\01272_DEGMEC_24251"
# ❌ output_dir = "General\\RBT\\2025-2026\\..."
```

---

## `ORDER BY` obligatoire

Le moteur Python ne garantit pas l'ordre des lignes. Chaque fonction SQL doit imposer son propre `ORDER BY` :

```sql
ORDER BY "ID__PLACET" ASC, "NO_MICRO_P" ASC
```

---

## Résilience

Une feuille qui échoue ne casse pas le run complet.

- Si SQL échoue → `rows = []`, log, copie + upload du template vide
- Si écriture DBF échoue → fallback copie brute + upload
- Le pipeline continue toujours pour les autres exports

---

## Packs figés par année

Un pack livré ne se modifie jamais.

```
ddif/2025-2026/   ← figé
ddif/2026-2027/   ← copie + ajustements pour la nouvelle année
```

---

## Ajouter un nouvel export — checklist

1. Créer `sql/<EXPORT>.sql` avec la fonction respectant la signature standardisée
2. Ajouter l'entrée dans `config.yaml` (`install_file`, `function`, `cfg_from_payload` avec au minimum `user_ref1` et `id_projet`)
3. Vérifier que `ORDER BY` est présent
4. Vérifier les filtres STRICT (`user_ref1`, `region`, `ue`)
5. Tester : `python build_ddif_exports.py --payload-file test_payload.json`

---

## Voir aussi

- Architecture complète du moteur DDIF : `docs/ddif_architecture.md`
- Conventions d'écriture SQL (fetch, DDL, transactions) : `docs/AI_RULES/sql_rules.md`
- Conventions de nommage (fonctions SQL, query_name) : `docs/AI_RULES/naming_rules.md`
