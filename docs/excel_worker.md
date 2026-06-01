# Excel Worker
*Conversion Excel → PDF via Excel Desktop dans une session utilisateur Windows*

---

# 1. Rôle et contrainte fondamentale

L'`excel_worker.py` est un processus autonome qui tourne **dans une session utilisateur Windows active** (RDP ou session console). Il ne peut pas tourner comme service NSSM headless : la conversion Excel → PDF repose sur COM automation (`excel_to_pdf.py`), qui exige qu'Excel Desktop soit disponible dans la session.

Ce que le worker fait en boucle :
1. Scanne `PDF_QUEUE_DIR` pour des fichiers `job_*.json` avec `status == "pending"`
2. Télécharge le fichier Excel depuis SharePoint (Graph)
3. Convertit Excel → PDF via Excel Desktop (feuille `Parcelle` par défaut, fallback si absente)
4. Upload le PDF vers SharePoint (Graph)
5. Appelle `register_kizeo_export.py` pour journaliser dans `app.kizeo_export_logs`
6. Archive le job dans `archive/` (succès) ou `error/` (échec)

---

# 2. Flux complet

```
Make → Flask → download_kizeo_file.py
                        ↓
               crée job_*.json (status=pending)
               dans PDF_QUEUE_DIR
                        ↓
               excel_worker.py (session Desktop)
                  ├── download xlsx depuis SharePoint
                  ├── convert xlsx → pdf (Excel COM)
                  ├── upload pdf vers SharePoint
                  └── appelle register_kizeo_export.py
                              ↓
                     app.kizeo_export_logs (BD)
```

---

# 3. Structure des répertoires

```
scripts/pdf_queue/       ← PDF_QUEUE_DIR (par défaut)
 ├── job_<id>.json       ← jobs en attente (status=pending)
 ├── tmp/                ← fichiers xlsx/pdf temporaires (nettoyés après conversion)
 ├── archive/            ← jobs traités avec succès
 └── error/              ← jobs en erreur

logs/
 ├── excel_worker.log            ← log rotatif (5 Mo × 5 fichiers)
 ├── excel_worker.lock           ← lock single-instance
 └── excel_worker_heartbeat.json ← heartbeat (réécrit à chaque boucle)
```

---

# 4. Format d'un job JSON

Créé par `download_kizeo_file.py`, consommé par le worker.

```json
{
  "status": "pending",
  "form_id": "880205",
  "data_id": 12345,
  "export_id": "abc123",
  "user_ref1": "ABIFOR",
  "coop_directory": "ABIFOR",
  "year_suffix": "2025-2026",
  "ue": "UE-01",
  "region": "R01",
  "bd": "chlorofile2",
  "excel_filename": "ABIFOR_UE01_2025-2026.xlsx",
  "sp_excel_rel_path": "ABIFOR/2025-2026/880205/ABIFOR_UE01_2025-2026.xlsx",
  "sp_pdf_rel_path": "ABIFOR/2025-2026/880205/ABIFOR_UE01_2025-2026.pdf"
}
```

Après traitement, le worker ajoute : `status`, `done_at` (ou `error_message` + `error_at`), `sheet_used`, `sheet_fallback_used`, `excel_size_bytes`, `pdf_size_bytes`.

---

# 5. Heartbeat

Le fichier `logs/excel_worker_heartbeat.json` est réécrit à chaque boucle (taille constante) :

```json
{
  "timestamp_utc": "2025-05-28T14:32:01.123456+00:00",
  "pid": 1234,
  "hostname": "SRV-FLASKAPP",
  "status": "running"
}
```

`status` peut être `"running"` ou `"stopped"`. Pour vérifier si le worker est vivant, contrôler que `timestamp_utc` est récent (< quelques secondes si `WORKER_SLEEP_SECONDS = 3`).

---

# 6. Variables d'environnement

| Variable | Défaut | Description |
|---|---|---|
| `PDF_QUEUE_DIR` | `scripts/pdf_queue/` | Répertoire des jobs JSON |
| `PDF_TMP_DIR` | `scripts/pdf_queue/tmp/` | Fichiers xlsx/pdf temporaires |
| `EXCEL_WORKER_HEARTBEAT_FILE` | `logs/excel_worker_heartbeat.json` | Fichier de heartbeat |
| `WORKER_SLEEP_SECONDS` | `3` | Pause entre les scans (secondes) |
| `LOG_DIR` | `logs/` | Répertoire des logs |

---

# 7. Lancer le worker

Le worker doit être démarré **dans la session RDP active** sur le serveur.

**Démarrage manuel :**

```powershell
cd C:\srv\flaskapp
.venv\Scripts\python.exe scripts\excel_worker.py
```

**Via Task Scheduler (recommandé) :**
- Déclencheur : Au démarrage de session / À la connexion de l'utilisateur
- Action : `C:\srv\flaskapp\.venv\Scripts\python.exe scripts\excel_worker.py`
- Répertoire de démarrage : `C:\srv\flaskapp`
- Important : cocher "Exécuter seulement si l'utilisateur est connecté"

**Single-instance** : si une instance tourne déjà, le second lancement s'arrête immédiatement (lock sur `excel_worker.lock`).

---

# 8. Debug

**Le worker ne traite pas les jobs :**
- Vérifier que `excel_worker_heartbeat.json` existe et que `timestamp_utc` est récent
- Si `status == "stopped"` → le worker est arrêté, le relancer
- Vérifier `logs/excel_worker.log`

**Les jobs tombent en `error/` :**
- Lire le champ `error_message` dans le JSON d'erreur (`pdf_queue/error/job_*.json`)
- Erreur `ExcelConversionError` → problème Excel Desktop (Excel pas installé, fichier corrompu, feuille introuvable)
- Erreur Graph → problème d'authentification ou de chemin SharePoint

**Relancer un job en erreur manuellement :**
```powershell
# Copier le job depuis error/ vers pdf_queue/ et remettre status à "pending"
```
Éditer le JSON : `"status": "pending"`, supprimer `error_message` et `error_at`, remettre dans `pdf_queue/`.

---

# 9. Voir aussi

- [pipeline_exports.md](pipeline_exports.md) — flux complet Excel/PDF
- [scripts_overview.md](scripts_overview.md) — rôle de chaque script
- [sharepoint_structure.md](sharepoint_structure.md) — chemins SharePoint
- [troubleshooting.md](troubleshooting.md) — debug général
