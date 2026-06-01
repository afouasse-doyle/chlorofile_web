# Structure SharePoint (Microsoft Graph)

Toute la persistance fichier de l'application passe par Microsoft Graph / SharePoint.  
Tous les chemins sont **relatifs sous `GRAPH_SP_ROOT_DIR`** (= `General/`).  
Ne jamais préfixer avec `General\` dans le code ou les payloads.

> **Séparateurs :** `graph_storage.py` normalise automatiquement `\` → `/` via `_norm_rel()`. Les deux styles sont acceptés — il n'y a pas de style obligatoire.

> **Règles de code :** voir `docs/AI_RULES/graph_sharepoint_rules.md` pour les règles à appliquer lors de l'écriture ou la modification de scripts utilisant Graph.

---

## Règles générales

| Variable | Valeur | Source |
|---|---|---|
| `coop_code` | Code court coop (ex: `RBT`, `CFNC`) | `app.coops.directory` résolu via `user_id` → `user_ref1` |
| `year_suffix` | Clé d'année (ex: `2025-2026`) | Payload Make |
| `form_name` | Nom du formulaire | `app.kizeo_form_exports`, conservé tel quel (pas de sanitization) |
| `region` | Code région (ex: `01`, `MAU`) | Payload Make (optionnel) |
| `ue` | Unité d'échantillonnage (ex: `2023-11161_-ELS3-502`) | Payload Make (optionnel) |

> `coop_code` est le code court (ex: `RBT`) depuis la migration OneDrive local → Graph.  
> L'ancienne colonne `app.coops.directory` contenait un chemin de fichier — elle contient maintenant le code coop.

---

## 1. Exports Kizeo (Excel et PDF)

**Script** : `download_kizeo_file.py` (via `name_builder.py`)

### Structure

```
General/
└── <coop_code>/
    └── <year_suffix>/
        └── <form_name>/
            ├── <filename>                        (sans région ni UE)
            ├── <ue>/
            │   └── <filename>                    (UE seul)
            ├── <region>/
            │   └── <filename>                    (région seule)
            └── <region>/
                └── <ue>/
                    └── <filename>                (région + UE)
```

### Exemples concrets

```
RBT/2025-2026/Formulaire nettoyage/01/2023-11161_-ELS3-502/nettoyage_123.xlsx
CFNC/2025-2026/Inventaire parcelle/MAU/inventaire_456.xlsx
RBT/2025-2026/Suivi traitement/suivi_789.pdf
```

### Notes

- Le nom de fichier (`filename`) est lu depuis l'en-tête HTTP `Content-Disposition` de l'API Kizeo — il n'est pas renommé.
- Excel et PDF suivent la même structure de dossiers ; seule l'extension diffère.
- Pour un export PDF avec conversion Desktop, `download_kizeo_file` crée un job `pdf_queue/job_<ts>.json` ; le fichier PDF est uploadé par `excel_worker.py` après conversion.

---

## 2. Rapports d'exécution générés (`RE_<UE>.xlsx`)

**Script** : `build_rapport_execution.py` (déclenché automatiquement par `register_kizeo_export.py`)

### Structure

```
General/
└── <coop_code>/
    └── <year_suffix>/
        └── <form_name>/
            └── <region>/
                └── <ue>/
                    └── RE_<UE>.xlsx
```

### Exemple concret

```
RBT/2025-2026/Formulaire nettoyage/01/2023-11161_-ELS3-502/RE_2023-11161_-ELS3-502.xlsx
```

### Notes

- Le chemin cible est `output_dir/RE_<UE>.xlsx` — `output_dir` est le même que celui de l'export Excel associé.
- Déclenché automatiquement par `register_kizeo_export` dès que `ue`, `region`, `output_dir`, `form_id`, `year_suffix` et `form_name` sont tous présents dans la payload.
- Recalculé à chaque INSERT, UPDATE et DELETE d'export pour toujours refléter l'état courant de la BD.

---

## 3. Modèles rapport d'exécution (source, lecture seule)

**Script** : `build_rapport_execution.py` (lecture uniquement — le modèle n'est jamais modifié)

### Structure

```
General/
└── 1-Gestion/
    └── rapport_execution/
        └── <year_suffix>/
            └── <form_name>/
                └── <region>/
                    └── <modele>.xlsx
```

### Exemple concret

```
1-Gestion/rapport_execution/2025-2026/Formulaire nettoyage/01/modele_RE.xlsx
```

### Notes

- `build_rapport_execution` cherche le modèle par glob `*.xlsx` dans ce dossier.
- Le modèle est téléchargé en local temporaire, rempli, puis re-uploadé sous un nom différent (`RE_<UE>.xlsx`) dans le dossier de l'UE — le fichier modèle source n'est jamais touché.

---

## 4. Exports DDIF (DBF)

**Script** : `build_ddif_exports.py` (appelé en subprocess par `ddif_name_builder.py`)

### Structure

```
General/
└── <coop_code>/
    └── <year_suffix>/
        └── <form_name>/
            └── <region>/
                ├── ddif/
                │   └── <template>.dbf            (sans UE)
                └── <ue>/
                    └── ddif/
                        └── <template>.dbf        (avec UE)
```

### Exemple concret

```
RBT/2025-2026/Formulaire nettoyage/01/ddif/TRAITEMENT.dbf
RBT/2025-2026/Formulaire nettoyage/01/2023-11161_-ELS3-502/ddif/TRAITEMENT.dbf
```

### Notes

- Le sous-dossier `ddif/` est toujours présent — il distingue les DBF des autres fichiers du dossier UE.
- Les noms de fichiers DBF correspondent aux noms de templates dans `scripts/ddif/<year_suffix>/<form_name>/<region>/templates/`.
- Les packs DDIF (templates, SQL, config) sont locaux au serveur (`scripts/ddif/`) — seule la sortie est uploadée sur SharePoint.
- Une failure sur un template n'arrête pas les autres : chaque DBF est traité indépendamment.

---

## 5. Fichiers data manuelle (sources)

**Scripts** : `upsert_data_manuelle_db.py`, `create_kizeo_lists_excel.py`

### Structure

Pas de structure fixe imposée par l'application. Les chemins sont enregistrés dans la base PostgreSQL et retournés par la fonction :

```sql
SELECT file_path FROM app.get_data_manuelle_files(<year_suffix>)
```

Les scripts téléchargent chaque fichier depuis le chemin SharePoint relatif retourné par cette requête.

### Notes

- Les fichiers sont typiquement des classeurs Excel (`.xlsx`, `.xlsm`) multi-feuilles.
- `upsert_data_manuelle_db.py` consomme les feuilles `prescription`, `parcelle`, `secteur_intervention_reb`.
- `create_kizeo_lists_excel.py` consomme les mêmes fichiers source pour alimenter les listes Kizeo (pipeline listes).
- L'emplacement SharePoint réel de ces fichiers est géré hors de l'application (ex: déposés manuellement par les coops).

---

## Récapitulatif des chemins

| Type de fichier | Chemin relatif sous `General/` |
|---|---|
| Export Kizeo Excel/PDF | `<coop>/<year>/<form>/[<region>/][<ue>/]<filename>` |
| Rapport d'exécution | `<coop>/<year>/<form>/<region>/<ue>/RE_<UE>.xlsx` |
| Modèle RE (source) | `1-Gestion/rapport_execution/<year>/<form>/<region>/<modele>.xlsx` |
| Export DDIF | `<coop>/<year>/<form>/<region>/[<ue>/]ddif/<template>.dbf` |
| Data manuelle (source) | Chemins libres, indexés dans `app.data_manuelle_files` (BD) |

---

## Voir aussi

- [pipeline_exports.md](pipeline_exports.md) — pipeline complet Excel/PDF (name_builder → download → register → rapport)
- [ddif_architecture.md](ddif_architecture.md) — architecture détaillée du moteur DDIF
- [pipeline_data_manuelle.md](pipeline_data_manuelle.md) — import des données manuelles
- [payloads_by_script.md](payloads_by_script.md) — référence des champs de payload
