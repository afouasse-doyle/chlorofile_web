# ROADMAP / Suivi — Chlorofile Web

Suivi de l'avancement du portail. Mettre à jour à chaque étape franchie.
Légende : ✅ fait · 🚧 en cours · ⬜ à faire

---

## Phase 0 — Fondations (modèle de données + backend de base)

| Étape | Statut | Notes |
|---|---|---|
| Schéma `appweb` (SQL complet) | ✅ | `docs/chlorofile_web/schema_appweb.sql` |
| Architecture documentée (ADRs) | ✅ | `docs/chlorofile_web/architecture.md` |
| Structure FastAPI (config, db, models) | ✅ | `backend/app/` |
| Service d'import DBF — preview | ✅ | `backend/app/services/dbf_import.py` (priority-based) |
| Staging des lignes (import_batch_rows) | ✅ | JSONB raw + normalized |
| Authentification (JWT + bcrypt) | ✅ | `backend/app/core/security.py`, `routers/auth.py` |
| Sessions serveur (idle + absolu + révocation) | ✅ | table `appweb.user_sessions` |
| Anti-brute-force login | ✅ | table `appweb.login_attempts` |
| Gestion comptes (admin fqcf_admin) | ✅ | `GET/POST/PATCH /auth/users` |

## Phase 1 — Mise en service & test du backend

| Étape | Statut | Notes |
|---|---|---|
| Initialiser un dépôt git séparé | 🚧 | détacher du `.git` de flaskapp |
| Installer les dépendances backend | ⬜ | `pip install -r backend/requirements.txt` |
| Appliquer `schema_appweb.sql` sur `chlorofile2` | ⬜ | crée le schéma `appweb` |
| Créer le 1er admin (CLI) | ⬜ | `python -m scripts.create_user` |
| Lancer le backend (uvicorn) + tester via /docs | ⬜ | Swagger UI, pas besoin du frontend |
| Tester login + import preview de bout en bout | ⬜ | upload d'un DBF réel |

## Phase 2 — Commit réel (écriture métier)

| Étape | Statut | Notes |
|---|---|---|
| `UeService.upsert_from_batch()` | ⬜ | distinct UE → upsert `appweb.ue` |
| `ParcelleService.upsert_from_batch()` | ⬜ | upsert + soft-delete des parcelles disparues |
| Brancher le commit dans `/imports/{uuid}/commit` | ⬜ | remplace le stub actuel |
| Migrations Alembic | ⬜ | versionner les évolutions de schéma |

## Phase 3 — Validation & édition métier

| Étape | Statut | Notes |
|---|---|---|
| Service de validation (validation_rules) | ⬜ | écrit `validation_results` |
| Routes UE / parcelles (GET/PATCH) | ⬜ | + edit_history |
| Génération Kizeo (simulée) | ⬜ | `kizeo_generation_log` |

## Phase 4 — Frontend

| Étape | Statut | Notes |
|---|---|---|
| Squelette React + TypeScript + MUI | ⬜ | menu gauche, tables filtrables |
| Écran login | ⬜ | |
| Écran import DBF (preview → commit) | ⬜ | |
| Écrans UE / parcelles / validation | ⬜ | |

---

## Points ouverts à trancher

- Multi-coop pour `fqcf_admin` (sélection de coop) — non implémenté
- Politique de complexité des mots de passe côté API
- Confirmation : champs manuels exacts sur `ue` (au-delà de gradient_intensite, rayon, stocking_av_tr)
- Confirmation : `PLT_ADMIS` → `plant_ha` ou `plant_max`
