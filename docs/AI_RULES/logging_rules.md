# Règles de logging

## Règle absolue : SUCCÈS compact, ÉCHEC détaillé

Cette règle a priorité sur toutes les autres.

Il y a deux et seulement deux issues possibles pour un script :

- **SUCCÈS** : le script passe entièrement → logs compacts, 3 à 5 lignes INFO maximum.
- **ÉCHEC** : une étape plante → détail complet immédiatement visible.

**Il n'y a pas de mode DEBUG.** En production, les logs sont toujours au niveau INFO. Jamais de troisième mode, jamais de relance en debug pour comprendre un échec — l'ÉCHEC doit être auto-suffisant.

Un script qui produit trop de logs en succès est non conforme.

---

## SUCCÈS — pattern attendu

```
START create_kizeo_user_structure bd=chlorofile2 load_pg=True
FETCH users OK count=1200
FILES OK json=kizeo_users.json csv=kizeo_users.csv xlsx=yes
PG OK target=app.kizeo_users upserted=1200 alive=1200
DONE ✔ users=1200 pg_loaded=True pg_rows=1200
```

Règles :
- La première ligne `START` donne le contexte minimal (script + paramètres clés).
- Chaque grand bloc métier produit une ligne résumé.
- La dernière ligne `DONE ✔` résume les compteurs utiles.
- Aucun détail interne, aucun JSON complet, aucun payload.

**Grands blocs métier valides :**
- `FETCH` / `DOWNLOAD` — appel API ou téléchargement
- `FILES` — écriture de fichiers (résumé global, pas fichier par fichier)
- `PG` / `UPSERT` / `REGISTER` — opération PostgreSQL
- Appel d'un sous-script
- Upload SharePoint

**Ne jamais loguer comme bloc métier :**
- Validation payload
- Lecture des variables d'environnement
- Connexion BD (`pg_connect`)
- `ensure_table` / DDL
- Préparation interne de variables

---

## ÉCHEC — pattern attendu

```
START create_kizeo_user_structure bd=chlorofile2 load_pg=True
PG sync failed
Traceback (most recent call last):
  ...
```

Règles :
- Identifier clairement l'étape globale qui a planté.
- Fournir le traceback si exception Python (`logger.exception`).
- Fournir returncode + stdout/stderr tronqués si subprocess échoué.

---

## `logger.exception()` vs `logger.error()`

- **`logger.exception("...")`** : dans un bloc `except` — capture automatiquement le traceback.
- **`logger.error("...")`** : pour les échecs sans exception active (ex : `returncode != 0`).

```python
# ✅ Exception Python réelle
try:
    users = list_users(base_url, token, logger)
except Exception:
    logger.exception("FETCH users failed")
    raise

# ✅ Subprocess échoué
if returncode != 0:
    logger.error("upsert failed rc=%s", returncode)
    logger.error("stdout (failure): %s", stdout[:1000])
    logger.error("stderr (failure): %s", stderr[:2000])
```

---

## Catch global dans `handle()`

Chaque `handle()` enveloppe tout son corps dans un try/except pour identifier le script dans les logs :

```python
def handle(payload, logger):
    try:
        # ... tout le code ...
    except Exception:
        logger.exception("FAILED create_kizeo_user_structure")
        raise
```

---

## Appels subprocess

**Avant l'appel :**
```python
logger.info("Invoking upsert_data_postgresql form_id=%s", form_id)
```

**Après l'appel :**
- `returncode == 0` : résumé court (stdout JSON si possible, sinon max 200-300 chars)
- `returncode != 0` :
  - `logger.error("<script> failed rc=%s", returncode)`
  - `logger.error("stdout (failure): %s", stdout[:1000])` si non vide
  - `logger.error("stderr (failure): %s", stderr[:2000])` si non vide

Ne pas re-dumper une sortie déjà streamée en live.

**Chemin du sous-script — toujours relatif au script courant :**
```python
# ✅
script_path = Path(__file__).parent / "upsert_data_postgresql.py"

# ❌
script_path = "C:/srv/flaskapp/scripts/upsert_data_postgresql.py"
```

---

## Appels inter-scripts via `handle()` direct

```python
child_logger = logger.getChild("download_kizeo_file")
res = download_kizeo_file.handle(enriched_payload, child_logger)
```

Ne pas reconfigurer le logger enfant — il hérite de la configuration du dispatcher.

---

## Ce qu'on NE logue JAMAIS en succès

- Payloads JSON complets
- stdout/stderr complets d'un subprocess
- Commandes subprocess complètes
- Détails de chaque étape interne
- Un stderr normal d'un subprocess qui a réussi (ne pas transformer en WARNING)

---

## Retour de `handle()`

**Succès :**
```python
return {
    "status": "ok",
    "count": len(users),
    "pg_loaded": pg_loaded,
    "pg_rows": pg_rows,
    "bd": p.bd,
}
```

**Échec :**
```python
return {
    "status": "error",
    "step": "build_names",
    "error": str(e),
    "form_id": form_id,
    "data_id": data_id,
}
```

Ne jamais retourner stdout/stderr complets, payload complète, ou gros JSON internes.
Les détails complets vont dans les **logs**, pas dans le dict de retour.

---

## Configuration du logger

Ne jamais appeler `logging.basicConfig(...)` dans le corps principal d'un script dispatcher.

```python
# ✅ Autorisé uniquement dans le bloc __main__
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    log = logging.getLogger("mon_script")

# ❌ Interdit à la racine du module ou dans handle()
logging.basicConfig(...)
```

En mode dispatcher Flask, utiliser exclusivement le `logger` fourni en argument à `handle(payload, logger)`.

`safe_db.py` gère son propre `LOG = logging.getLogger("safe_db")` — ne pas interférer.

---

## Taille des blocs en erreur

- stdout d'un subprocess : tronquer à ~1000 caractères
- stderr d'un subprocess : tronquer à ~2000 caractères
- Résumé texte en succès : max 200-300 caractères

---

## Voir aussi

- Structure des scripts et contrat de `handle()` : `docs/AI_RULES/python_script_standard.md`

## Voir aussi

- Contrat de retour de handle() et structure des scripts : `docs/AI_RULES/python_script_standard.md`
