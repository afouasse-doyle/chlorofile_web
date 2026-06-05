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
| `ParcelleService.upsert_from_batch()` | ✅ | `pds_service.commit_batch` : upsert + soft-delete (wipe scopé par UE) + gate « UE valide ». Testé (14 accrochées, wipe 8/6) |
| Brancher le commit dans `/imports/{uuid}/commit` | ✅ | UE → ue_service ; **PDS → pds_service** (plus de 501) |
| Migrations Alembic | ⬜ | versionner les évolutions de schéma (toujours à faire) |

## Phase 3 — Validation & édition métier

| Étape | Statut | Notes |
|---|---|---|
| Service de validation (le « juge ») | ✅ | `validation_service.validate_ue` : R/O/C + conditionnels (year/region/traitement). Pur. Testé sur UE-050 |
| Modèle `FieldDefinition` + correctif `ValidationRule` | ✅ | `field_definition.py` créé ; `ValidationRule` complété (rule_name, region, traitement_match) |
| Correctif seed `code_dica` → `source=auto` | ✅ | seed + base ; était `manuel` à tort (faussait le statut) |
| Routes UE (GET) | ✅ | `GET /ue/`, `GET /ue/{uuid}`, **`GET /ue/{uuid}/validation`** |
| Route UE (PATCH) + edit_history | ✅ | bornes min/max (422), audit, recalcul statut, re-dérivation traitement. Testé (3 cas) |
| Gate PDS « UE valide » | ✅ | branché dans `pds_service` (3 compteurs de skip) |
| Génération Kizeo (simulée) | ⬜ | `kizeo_generation_log` — Phase 4A (réutilise le juge en pré-vol) |

## Phase 4 — Frontend

➡️ **Détail complet dans [`ROADMAP_FRONTEND.md`](ROADMAP_FRONTEND.md)** (sous-phases 4A endpoints prérequis · 4B fondations · 4C écrans).
Spec UI exhaustive : [`FRONTEND_NOTES.md`](FRONTEND_NOTES.md).

| Sous-phase | Statut | Résumé |
|---|---|---|
| 4A — Endpoints backend prérequis | ⬜ | `form-schema` (#1), `/years`, `/parcelles`, Kizeo, dashboard, comparaison conflits |
| 4B — Fondations front | ⬜ | Vite+React+TS+MUI, AuthContext, YearContext, layout, react-query |
| 4C — Écrans | ⬜ | login → import → liste UE → **édition UE** → parcelles → validation → Kizeo → admin |

---

## Points ouverts à trancher

- Multi-coop pour `fqcf_admin` (sélection de coop) — non implémenté (bloque les routes coop pour un admin global)
- Politique de complexité des mots de passe côté API
- **Durcissement non-destructif de `ue_service.commit_batch`** : ne jamais écraser avec une valeur vide ; sortir `region` (champ manuel) de `_UE_FIRST_FIELDS` — à faire avant d'ouvrir les ré-imports (voir FRONTEND_NOTES §8/§12)
- Migrations Alembic jamais initialisées (schéma appliqué à la main jusqu'ici)
- RLS PostgreSQL différée à la toute fin
