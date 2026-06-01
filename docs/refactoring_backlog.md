# Backlog refactoring

Tâches techniques identifiées lors de la formalisation des règles AI.
À traiter script par script, de façon contrôlée.

---

## 1. `handle()` — catch global ne doit pas re-raise

**Règle établie :** le catch global de `handle()` retourne toujours `{"status": "error", ...}` — jamais `raise`.

**Pourquoi :** le dispatcher Flask est asynchrone (retourne 202 immédiatement). Les exceptions non capturées sont loggées par le dispatcher mais le comportement est moins structuré qu'un return dict explicite.

**Référence :** `docs/AI_RULES/python_script_standard.md` — section "Contrat de retour de handle()"

**Scripts à corriger :** audit à faire — chercher les `handle()` qui font `raise` dans leur catch global plutôt que `return {"status": "error", ...}`.

```bash
# Recherche rapide dans les scripts
grep -n "raise$" scripts/*.py
```

---

## 2. `query_name` dans `exec_sql` — format `<objet>_<opération>`

**Règle établie :** format `<objet_ou_contexte>_<opération>` en snake_case.

**Pourquoi :** cohérence des logs SQL, facilite la lecture des traces de performance et des erreurs.

**Référence :** `docs/AI_RULES/naming_rules.md` — section "query_name dans exec_sql"

**Périmètre :** tous les appels `exec_sql(...)` dans `scripts/` et `scripts/safe_db.py`.

**À faire :** audit de tous les `query_name` existants et mise à jour vers le nouveau format.

---

## 3. `safe_db.py` — mise à niveau des bannières de section + anomalie `fetch_form_name_for_form_id`

**Règle établie :** `safe_db.py` est organisé en sections nommées avec bannières annotées (Scripts + Tables). Voir `docs/AI_RULES/sql_rules.md` — section "Organisation interne de `safe_db.py`".

**Travail à faire :**

**3a. Remplacer tous les séparateurs `# ----` existants par le format officiel :**

```python
# ====================================================================
# SECTION : <nom>
# Scripts : <scripts>
# Tables  : <tables>
# ====================================================================
```

Sections à créer (dans l'ordre) :

| Section | Scripts | Tables |
|---|---|---|
| Infrastructure | tous les scripts | — |
| Lookups partagés | `name_builder.py`, `ddif_name_builder.py`, `register_kizeo_export.py` | `app.kizeo_form_exports`, `app.kizeo_users`, `app.coops` |
| Kizeo users | `create_kizeo_user_structure.py` | `app.kizeo_users` |
| Kizeo export logs | `register_kizeo_export.py` | `app.kizeo_export_logs` |
| Data manuelle | `upsert_data_manuelle_db.py` | `app.prescriptions`, `app.secteur_intervention_reb`, `app.parcelles`, `app.data_manuelle_files` |
| Catalogue Kizeo | `sync_kizeo_catalog.py` | `app.kizeo_forms`, `app.kizeo_lists`, `app.kizeo_form_fields`, `app.kizeo_form_exports`, `app.kizeo_form_lists` |

**3b. Corriger `fetch_form_name_for_form_id` (ligne ~938) :**
Utilise un curseur brut (`with conn.cursor()`) au lieu de `exec_sql` — contourne le logging SQL et la politique de rollback automatique. Réécrire via `exec_sql(..., fetch="one", query_name="fetch_form_name_for_form_id")`.

**Périmètre :** `scripts/safe_db.py` uniquement.
**Contrainte :** modifications structurelles/cosmétiques uniquement pour 3a — aucun changement de logique. Correction fonctionnelle pour 3b.

---

---

## 4. `payload_models.py` — mise à niveau complète

```
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
payload_models.py
-----------------
Modèles Pydantic centralisés pour valider / nettoyer les payloads reçues
par les différents scripts Python du serveur Flask (name_builder, upsert,
export_kizeo, register_kizeo_export, etc.).

Objectif :
  - Séparer la validation / sanitisation des payloads JSON reçues par le dispatcher.
  - Garantir des entrées propres, typées, normalisées, avant toute logique métier.
  - Offrir une bibliothèque de modèles réutilisables pour tous les scripts.

=====================================================================
VALIDATION Pydantic — RÈGLE GÉNÉRALE (TOUS LES SCRIPTS)
=====================================================================

Objectif unique de payload_models.py
-----------------------------------
Ce fichier est LA couche contractuelle d'entrée pour TOUTES les payloads JSON
qui arrivent du dispatcher (Make/Kizeo/autres).

On valide ici pour 2 raisons seulement :

1) Sécurité (anti-injection / anti-entrée sale)
   - Empêcher qu'un champ "libre" (string) contienne des trucs dangereux ou cassants :
     quotes, slash, backslash, caractères weird, path traversal, etc.
   - Empêcher les types inattendus (ex : "mtm" = "lol", nb_0 = "DROP TABLE", etc.)
   - Empêcher les keys surprises :
       extra="forbid" => si une clé n'est pas déclarée, ça plante.
       (c'est volontaire : ça force à garder un contrat clair)

2) Contrat / stabilité (éviter le spaghetti)
   - Quand tu ajoutes une variable dans Make :
       -> tu DOIS la déclarer dans le modèle Pydantic correspondant
       -> sinon ça casse immédiatement (et c'est voulu)
   - Ça évite de "laisser passer n'importe quoi" et de déboguer 3 scripts plus loin.

=====================================================================
RÈGLE D'OR
=====================================================================

👉 1 SEULE validation à l'entrée du script (handle(payload) / main())

PAS de "2e validation" plus loin dans le pipeline,
sauf si une entrée directe du dispatcher peut apparaître plus tard.

Une fois validé :
👉 le dict est considéré comme "propre" pour toute la suite.

=====================================================================
IMPORTANT : CHAMPS CALCULÉS / ENRICHIS
=====================================================================

Certains champs ne viennent PAS de la payload externe (ex : calcul DB,
enrichissement, path résolu, etc.).

Ces champs NE DOIVENT PAS être dans le modèle d'entrée, parce que :
- ils ne sont pas fournis par Make
- ils sont produits après validation
- sinon tu mélanges validation et logique métier

👉 payload_models = INPUT ONLY

=====================================================================
COMMENT AJOUTER UNE VARIABLE (PROCESS STANDARD)
=====================================================================

1) Ajouter le champ dans LE modèle du script concerné :
   - type strict (int, bool, Literal, etc.)
   - ou constr(pattern=...) pour les codes

2) Ajuster le script SEULEMENT si la variable est utilisée

3) Si extra="forbid" :
   - toute clé non déclarée fera planter (c'est voulu)

=====================================================================
PATTERNS RECOMMANDÉS (PROD SAFE)
=====================================================================

- IDs numériques         : r"^\\d+$"
- Codes courts           : r"^[A-Z]{2,4}$" ou r"^[A-Za-z0-9_-]+$"
- Flags (ind_action)     : r"^[A-Z]$"
- Bool métier            : Literal["Oui", "Non"]
- Champs optionnels      : Optional[...] + "" → None (normalisation)
- Paths                  : jamais free text non contrôlé

=====================================================================
NORMALISATION GLOBALE
=====================================================================

Toutes les classes héritent d'une base commune qui :
- trim les strings
- convertit "" → None
- empêche les valeurs vides ambiguës

👉 Résultat :
- payload cohérente
- moins de "if x == ''" dans les scripts
- moins de bugs silencieux

=====================================================================
MODE STRICT vs IGNORE
=====================================================================

Par défaut :
👉 extra="forbid" (STRICT)

- aucune clé inattendue autorisée
- garantit un contrat clair avec Make

Exception rare :
👉 extra="ignore"

- utilisé pour certains scripts legacy / enveloppes bruitées
- les champs inconnus sont ignorés

=====================================================================
REBUILD AUTOMATIQUE (IMPORTANT)
=====================================================================

Tous les modèles sont automatiquement rebuild à la fin du fichier :

👉 Plus besoin de model_rebuild() manuel
👉 Support complet de :
   - Literal
   - Union
   - alias
   - types avancés

=====================================================================
PHILOSOPHIE GLOBALE
=====================================================================

payload_models.py = sécurité + contrat + stabilité

On ne valide PAS pour "faire beau".

On valide pour :
- BLOQUER les entrées dangereuses
- FORCER un contrat explicite
- ÉVITER les bugs en aval

👉 Si ça casse ici, c'est une bonne chose.
"""
```

**À faire en même temps que le refactor :**
- Créer `docs/AI_RULES/payload_models_rules.md` à partir du docstring ci-dessus (version condensée et queryable)
- Ajouter l'entrée dans `CLAUDE.md` (tableau "Référence contextuelle") : `| Payloads / validation | docs/AI_RULES/payload_models_rules.md |`

---

## 5. `payload_models.py` — `user_ref1` injecté par le dispatcher

**Contexte :** Le dispatcher (`run_flask_server.py`) résout maintenant `user_id → user_ref1` via `app.kizeo_users` et injecte `user_ref1` dans la payload avant de passer au script.

**État actuel :** `user_ref1: Optional[str] = None` a été ajouté à **tous** les modèles pour éviter les crashes Pydantic (`extra="forbid"`).

**À faire lors de la refonte :**

- Pour les modèles où `user_id` est requis (`NameBuilderPayload`, `DdifNameBuilderPayload`) : envisager de rendre `user_ref1` requis (`str` non-Optional) une fois que l'injection dispatcher est garantie (résolution fail-safe → fatale).
- Pour les modèles qui utilisaient `fetch_user_ref1(conn, user_id)` dans leurs scripts : utiliser `p.user_ref1` directement et supprimer l'appel DB redondant.
- Documenter dans chaque modèle que `user_ref1` est **injecté par le dispatcher**, pas fourni par Make.

---

## Règles pour ce backlog

- Traiter un script à la fois, jamais de refactor global en une seule passe
- Respecter `docs/AI_RULES/patching_rules.md` pour chaque correction
- Tester après chaque script modifié avant de passer au suivant
