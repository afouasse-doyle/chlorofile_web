# Règles Microsoft Graph / SharePoint

> Référence complète : `docs/sharepoint_structure.md`

## Principe fondamental

- Toute persistance fichier passe par **`graph_storage.py`** — zéro appel direct à l'API Graph dans les scripts
- Zéro fichier permanent en local — utiliser `tempfile` pour les fichiers intermédiaires d'upload
- Zéro écriture locale permanente : tout va sur SharePoint

---

## Chemins — règles absolues

- Tous les chemins sont **relatifs sous `GRAPH_SP_ROOT_DIR`** (= `General/`)
- Ne **jamais** inclure `General\` ou `General/` comme préfixe dans un chemin passé aux fonctions de `graph_storage.py`
- `graph_storage.py` normalise automatiquement `\` → `/` via `_norm_rel()` — les deux styles de séparateur sont acceptés
- Exception : `sp_delete_file` tolère un chemin déjà préfixé par `General/` (il détecte et ne double pas)

```python
# ✅
sp_upload_file(tmp_path, "RBT/2025-2026/Formulaire/01/fichier.xlsx")

# ❌
sp_upload_file(tmp_path, "General/RBT/2025-2026/Formulaire/01/fichier.xlsx")
```

---

## Structure des chemins par type de fichier

| Type | Chemin relatif sous `General/` |
|---|---|
| Export Kizeo Excel/PDF | `<coop>/<year_suffix>/<form_name>/[<region>/][<ue>/]<filename>` |
| Rapport d'exécution | `<coop>/<year_suffix>/<form_name>/<region>/<ue>/RE_<UE>.xlsx` |
| Modèle RE (lecture seule) | `1-Gestion/rapport_execution/<year_suffix>/<form_name>/<region>/<modele>.xlsx` |
| Export DDIF | `<coop>/<year_suffix>/<form_name>/<region>/[<ue>/]ddif/<template>.dbf` |
| Data manuelle | Chemins libres indexés dans `app.data_manuelle_files` (BD) |

---

## `coop_code` — résolution obligatoire

`coop_code` est un **code court** (ex: `RBT`, `CFNC`) — jamais un chemin.

Il est résolu depuis la BD, jamais depuis la payload :

```python
user_ref1  = fetch_user_ref1(conn, data.user_id)
coop_code  = fetch_directory_from_coop(conn, user_ref1)
# coop_code = "RBT"  (pas "C:\srv\..." ni "General\RBT")
```

---

## API publique de `graph_storage.py`

| Fonction | Usage |
|---|---|
| `sp_upload_file(local_path, rel_path)` | Upload d'un fichier local vers SharePoint. Crée les dossiers parents si nécessaire. |
| `sp_download_file(rel_path, local_path)` | Téléchargement depuis SharePoint vers un fichier local. |
| `sp_ensure_folder(rel_dir)` | Crée récursivement un dossier SharePoint (idempotent). |
| `sp_list_children(rel_dir)` | Liste le contenu d'un dossier SharePoint. |
| `sp_delete_file(rel_path)` | Supprime un fichier. Retourne `False` si 404, `True` si supprimé. |
| `sp_put_text(rel_path, text)` | Upload d'un contenu texte directement. |

---

## Comportements à connaître

- **Retry automatique sur 423 Locked** — `graph_storage.py` réessaie 2 fois avec backoff (2s, 4s)
- **Refresh token automatique sur 401** — token recalculé une fois, puis la requête est rejouée
- **`sp_delete_file` retourne `False` sur 404** — ne pas traiter ça comme une erreur
- **`sp_upload_file` crée les dossiers parents** — pas besoin d'appeler `sp_ensure_folder` avant

---

## Fichiers temporaires pour l'upload

Ne jamais écrire en local de façon permanente. Toujours utiliser `tempfile` :

```python
import tempfile

with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
    tmp.write(content)
    tmp_path = tmp.name

try:
    sp_upload_file(tmp_path, rel_path)
finally:
    os.unlink(tmp_path)
```

---

## Variables d'environnement requises

```
GRAPH_TENANT_ID
GRAPH_CLIENT_ID
GRAPH_CLIENT_SECRET
GRAPH_SHAREPOINT_DRIVE_ID
GRAPH_SP_ROOT_DIR=General
```
