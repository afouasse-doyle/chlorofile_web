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
| Initialiser un dépôt git séparé | ✅ | dépôt propre, remote `chlorofile_web.git`, commit initial poussé (67 fichiers) |
| Installer les dépendances backend | ✅ | installées + testées ; passlib remplacé par bcrypt direct (incompat. bcrypt 5.0) |
| Appliquer `schema_appweb.sql` sur `chlorofile2` | ✅ | 12 tables + seed (22 alias, 6 règles), owner=chlorofile2_app |
| Créer le 1er admin (CLI) | ✅ | fqcf_admin créé (user_ref1=null) |
| Lancer le backend (uvicorn) + tester via /docs | ✅ | uvicorn OK, Swagger accessible |
| Tester login + /auth/me | ✅ | login + JWT + session + /auth/me 200 testés en réel |
| Tester import preview (upload DBF) | ✅ | testé avec PLR réel : 13 champs mappés, aperçu OK, lignes stagées |

## Phase 2 — Commit réel (écriture métier)

| Étape | Statut | Notes |
|---|---|---|
| `UeService.upsert_from_batch()` | ✅ | `ue_service.commit_batch` : somme ha, dérive traitement via dica_codes, upsert ue. Testé (7.27, REB) |
| `ParcelleService.upsert_from_batch()` | ⬜ | upsert + soft-delete des parcelles disparues |
| Brancher le commit dans `/imports/{uuid}/commit` | ✅ | UE → ue_service ; PDS → 501 (à venir) |
| Migrations Alembic | ⬜ | versionner les évolutions de schéma |

## Phase 3 — Validation & édition métier

| Étape | Statut | Notes |
|---|---|---|
| Service de validation (validation_rules) | ⬜ | écrit `validation_results` |
| Routes UE (GET) | ✅ | `GET /ue/`, `GET /ue/{uuid}` (scopé coop) |
| Routes UE (PATCH) / parcelles | ⬜ | + edit_history |
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
