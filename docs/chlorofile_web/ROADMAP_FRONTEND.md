# ROADMAP Frontend — Chlorofile Web

> Plan de sprint détaillé pour la **Phase 4 (frontend)**. Référencé depuis `ROADMAP.md`.
> La spec UI exhaustive (champs, listes, écrans, API) vit dans **`FRONTEND_NOTES.md`** — ce fichier-ci
> est le **plan d'exécution ordonné**, pas la spec. Lire les deux ensemble.
> Légende : ✅ fait · 🚧 en cours · ⬜ à faire · ⛔ bloqué par une dépendance. Mise à jour : 2026-06-02.

---

## Comment lire ce roadmap

Trois sous-phases, **dans l'ordre** :

1. **4A — Endpoints backend prérequis** : le frontend ne peut pas être propre sans eux. À faire **en premier**, côté FastAPI.
2. **4B — Fondations front** : stack, auth, contextes, layout. Le socle sur lequel tous les écrans s'appuient.
3. **4C — Écrans** : livrés **dans l'ordre de valeur métier**, chacun testable de bout en bout.

Principe directeur : **chaque item est livrable et testable seul**. On ne passe pas au suivant tant que le précédent n'est pas vérifié dans le vrai navigateur.

Rappel des 2 invariants (cf. `FRONTEND_NOTES.md`) :
- **Pack-driven** : aucun champ codé en dur — tout vient du `form-schema`.
- **Zéro plantage silencieux** : rien d'incomplet ne franchit la porte Kizeo.

---

## Phase 4A — Endpoints backend prérequis

> Côté `backend/` (FastAPI). Sans le #1, pas de formulaire dynamique possible.

| # | Endpoint | Statut | Définition de « fait » | Dépend de |
|---|---|---|---|---|
| 4A.1 | **`GET /ue/form-schema?year_suffix=`** | ⬜ | Renvoie `{year_suffix, fields[], lists{}, rules[]}` (cf. FRONTEND_NOTES §12). `fields` triés par `display_order`, dédup année>`*`. `lists` résout `list_options` + `code_dica` depuis `dica_codes`. | Modèle `ListOption` à créer · `FieldDefinition` ✅ déjà là |
| 4A.2 | **`GET /years`** | ⬜ | `DISTINCT year_suffix` de `field_definitions`, triées desc. | — |
| 4A.3 | **`GET /parcelles?ue_uuid=&include_inactive=`** | ⬜ | Parcelles d'une UE, scopé coop (via UE→user_ref1). Schéma `ParcelleOut`. | Modèle `Parcelle` ✅ |
| 4A.4 | **`POST /kizeo/generate`** (simulé) | ⬜ | Pré-vol via le juge : ne retient que les UE `is_valid` ; **retourne les UE bloquées + leurs `missing`** ; écrit `kizeo_generation_log` (status `simule`). N'envoie rien encore. | juge ✅ |
| 4A.5 | **`GET /dashboard`** (compteurs) | ⬜ | Compteurs UE par statut (non_valide/en_cours/valide) + N imports récents, pour l'année. | — |
| 4A.6 | **Comparaison de conflits au ré-import UE** + **durcissement non-destructif** | ⬜ | (a) un endpoint qui compare un lot stagé aux UE en base → classement 🟢/⚪/🟠 + écarts de champs auto. (b) `ue_service.commit_batch` ne doit **jamais** écraser avec une valeur vide ; **sortir `region` de `_UE_FIRST_FIELDS`** (champ manuel). | À faire **avant** d'ouvrir les ré-imports en usage réel |

**Note transverse 4A** : tous ces endpoints suivent les conventions existantes — scoping `user_ref1` depuis le token (`get_active_user_ref1`), schémas Pydantic en `schemas/`, logique en `services/`, jamais de SQL brut hors `safe_db`/ORM.

---

## Phase 4B — Fondations front

> Côté `frontend/` (nouveau). Rien de visible métier ici, mais tout en dépend.

| # | Item | Statut | Définition de « fait » |
|---|---|---|---|
| 4B.1 | **Bootstrap projet** | ⬜ | Vite + React + TypeScript + MUI. `npm run dev` sur :5173 (origine CORS déjà autorisée). Config d'URL d'API par env (`.env` dev=localhost:8000, prod=domaine). |
| 4B.2 | **Client API + intercepteur** | ⬜ | `axios` : ajoute `Bearer` automatiquement, gère **401 → logout/redirect login**. `@tanstack/react-query` pour cache/mutations. |
| 4B.3 | **AuthContext** | ⬜ | login (`POST /auth/login` **form-urlencoded**), stockage token, `GET /auth/me`, logout (`POST /auth/logout`), garde de route. Respecte le modèle de session (idle 30 min → 401). |
| 4B.4 | **YearContext** | ⬜ | Année active globale (liste via `GET /years`), persistée. Changer d'année recharge form-schema + listes UE. Tout écran lit l'année du contexte. |
| 4B.5 | **Layout + routing** | ⬜ | Coquille : menu gauche, en-tête avec sélecteur d'année + user/logout. Routes protégées. Menu admin masqué si `role != fqcf_admin`. |
| 4B.6 | **Hooks form-schema** | ⬜ | `useFormSchema(year)` (cache react-query) → fournit `fields/lists/rules` à tous les formulaires. Base du rendu piloté par métadonnées. |
| 4B.7 | **Composant `DynamicField`** | ⬜ | Rend le bon widget MUI selon `data_type` + `list_name` (cf. FRONTEND_NOTES §2). Gère required (R + C calculés), bornes min/max, lecture seule (`is_editable=false`). |

---

## Phase 4C — Écrans (ordre de valeur)

> Chaque écran = un incrément testable. Ordre choisi pour que la valeur métier arrive vite
> et que **l'édition UE** (le cœur) soit dispo dès que possible.

| # | Écran | Statut | Définition de « fait » | API |
|---|---|---|---|---|
| 4C.1 | **Login** | ⬜ | Form email/mdp → token → redirect. 401 ailleurs → revient ici. Gère 429 (anti-brute-force). | `/auth/login`, `/auth/me` |
| 4C.2 | **Liste UE** | ⬜ | Table filtrable (statut, traitement, region, recherche), **badges couleur** rouge/orange/vert, colonne « N manquants ». Clic → édition. | `GET /ue/?year_suffix=` |
| 4C.3 | **⭐ Édition UE** (le cœur) | ⬜ | Formulaire **généré** depuis form-schema, groupé par section (identité/prescription/requis/conditionnels/optionnels). ★ sur requis. **Cascade** : changer code_dica→traitement ou region réactive les conditionnels. Bornes client + 422 serveur inline. Save → PATCH → rafraîchit statut + manquants. | `form-schema`, `GET/PATCH /ue/{uuid}`, `/ue/{uuid}/validation` |
| 4C.4 | **Import DBF** | ⬜ | Upload (file + dbf_type + année) → **aperçu** (mapped/unmapped/missing + preview_rows + can_commit) → Commit → enchaîne sur la liste UE. | `POST /imports/upload`, `/imports/{uuid}/commit` |
| 4C.5 | **Détection de conflits au ré-import** | ⛔ | Dans l'écran import : classement 🟢/⚪/🟠, conflits champ auto base↔DBF, **défaut = garder base**, décision par conflit. | 4A.6 |
| 4C.6 | **Parcelles** | ⬜ | Liste des parcelles d'une UE (lecture seule), toggle actives/archivées. Explique le gate « UE valide » + le wipe. | 4A.3 |
| 4C.7 | **Validation (vue transversale)** | ⬜ | Toutes les UE de l'année avec statut + manquants, pour piloter la complétude avant Kizeo. | `GET /ue/` + `/validation` |
| 4C.8 | **Génération Kizeo** | ⛔ | Bouton « Générer » + **pré-vol** : affiche les UE bloquées et ce qui manque avant tout envoi. Simulé d'abord. | 4A.4 |
| 4C.9 | **Dashboard** | ⬜ | Compteurs par statut + imports récents (page d'accueil). | 4A.5 |
| 4C.10 | **Administration** | ⬜ | Gestion comptes (fqcf_admin only). Masqué sinon. | `GET/POST/PATCH /auth/users` |

---

## Dépendances en un coup d'œil

```
4A.1 form-schema ──► 4B.6 hooks ──► 4B.7 DynamicField ──► 4C.3 Édition UE (cœur)
4A.2 /years ──────► 4B.4 YearContext ──► (tous les écrans)
4A.3 /parcelles ──► 4C.6 Parcelles
4A.4 kizeo ───────► 4C.8 Génération Kizeo
4A.5 dashboard ───► 4C.9 Dashboard
4A.6 conflits ────► 4C.5 Détection de conflits   (⚠️ + durcir commit avant ré-imports réels)
4B.1-4B.5 socle ──► (tout 4C)
```

**Chemin critique** : `4A.1 → 4B.1 → 4B.2/3 → 4B.4 → 4B.6 → 4B.7 → 4C.1 → 4C.2 → 4C.3`.
Une fois là, on a déjà l'essentiel : se connecter, voir ses UE, et **les compléter**. Le reste (import, parcelles, Kizeo) s'ajoute par-dessus.

---

## Décisions de stack à confirmer avant 4B

- **MUI** comme lib de composants (présupposé dans FRONTEND_NOTES) — à valider.
- **react-hook-form** vs état manuel pour le form dynamique.
- **Build & déploiement cPanel/WHC** : build statique (`npm run build` → `dist/`) servi par cPanel. Vérifier le routing SPA (réécriture `.htaccess` vers `index.html`) et la base URL d'API en prod (CORS/HTTPS).
- Gestion du token : mémoire + refresh-on-401 (pas de localStorage si on veut limiter le XSS — à trancher).
