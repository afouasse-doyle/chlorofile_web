# État du projet — Chlorofile Web (handoff)

> Document de reprise. À lire en premier dans une nouvelle session pour comprendre où on en est sans tout réexpliquer. Dernière mise à jour : 2026-06-01.

---

## 1. Objectif

Portail web **indépendant** du système Flask existant (`C:\srv\flaskapp`), qui remplace les fichiers Excel `DATA_MANUELLE` et les macros VBA. Permet aux coops d'importer leurs DBF (prescriptions / parcelles), compléter les champs manquants, valider, et générer les listes Kizeo — **sans ouvrir DATA_MANUELLE**.

- Le portail = source de vérité. Excel devient une *sortie*, plus une source.
- Ne **jamais** toucher au schéma `app` ni au système flaskapp (référence seulement, copiée dans ce dossier).

## 2. Stack & emplacements

- Backend : **FastAPI + SQLAlchemy 2.0 + Pydantic v2 + psycopg2**, Python **3.13.7** (venv `.venv`)
- DB : PostgreSQL `chlorofile2`, schéma **`appweb`** (isolé de `app`). Hôte `159.203.59.12`, user `chlorofile2_app` (= `WEB_PG_USER`).
- `.env` partagé via `CHLOROFILE_ENV_PATH` (= `C:\srv\secrets\Chlorofile\.env`). Vars portail : `WEB_PG_USER`, `WEB_PG_PASS`, `WEB_SECRET_KEY` (≥32o).
- Code : `backend/app/` (config, database, dependencies, models/, schemas/, routers/, services/, core/)
- Docs/SQL : `docs/chlorofile_web/` (schema_appweb.sql + *_seed.sql + ce fichier + ROADMAP.md)
- Git : dépôt propre `github.com/afouasse-doyle/chlorofile_web` (séparé de flaskapp). `.gitignore` en liste blanche (suit backend/, docs/, CLAUDE.md ; ignore la copie flaskapp scripts/).
- Lancer : `cd backend && ..\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000` → http://localhost:8000/docs (Swagger = banc de test).

## 3. Schéma appweb (tables en base, fonctionnelles)

| Table | Rôle | Notes |
|---|---|---|
| `users` | login portail | email + password_hash (bcrypt). role: coop_user/coop_admin/fqcf_admin. user_ref1 = coop |
| `user_sessions` | sessions serveur | idle 30min + absolu 8h + révocation (logout) |
| `login_attempts` | anti-brute-force | fenêtre glissante par email + IP |
| `dbf_field_aliases` | mapping DBF→canonique | priority-based. **TY_TRAIT→code_dica** (pas traitement). 21 alias |
| `dica_codes` | réf code_dica→traitement | 149 codes (seed depuis scripts/dica.xlsm) |
| `list_options` | menus déroulants génériques | 305 valeurs (région, traitement_ps, code_ratf, equip_utilise… + méta-listes). Seed depuis validations Excel |
| `field_definitions` | catalogue de champs | 38 champs UE. data_type/source/requirement(R/O/C)/list_name/validation_rule/min/max. **Pack-driven par year_suffix** |
| `validation_rules` | règles conditionnelles | keyé (year_suffix, region, traitement, traitement_match). 4 règles nommées |
| `import_batches` | lots d'import | pending→preview→committed. dbf_type UE/PDS |
| `import_batch_rows` | lignes stagées | raw_data + normalized_data (JSONB) |
| `ue` | **entité principale** | 47 colonnes (alignée sur app.prescriptions). user_ref1, year_suffix |
| `parcelles` | parcelles (PDS) | pas encore alimentée |
| `edit_history`, `validation_results`, `kizeo_generation_log` | audit/log | prêtes, pas encore utilisées |

Seeds versionnés : `dica_codes_seed.sql`, `list_options_seed.sql`, `field_definitions_seed.sql`, `validation_rules_seed.sql`. `schema_appweb.sql` = DDL canonique synchronisé et validé (idempotent).

## 4. Endpoints API (fonctionnels)

- **Auth** : `POST /auth/login` (email+mdp→JWT), `POST /auth/logout`, `GET /auth/me`, `GET/POST/PATCH /auth/users` (fqcf_admin only)
- **Import** : `POST /imports/upload` (DBF→preview+staging), `POST /imports/{batch_uuid}/commit` (UE→écriture base ; PDS→501), `GET /imports/`
- **UE** : `GET /ue/`, `GET /ue/{ue_uuid}`
- Création de comptes = **fqcf_admin only** (pas d'auto-inscription). CLI `backend/scripts/create_user.py` pour le 1er admin. `hash_password.py` pour un INSERT manuel.

## 5. Modèle métier UE (validé avec le user)

- **DBF type = UE ou PDS** (pas PLR/RXF — ce sont tous des UE ; variations régionales absorbées par les alias).
- 1 UE = 1..n chantiers/secteurs d'intervention ; chaque ligne DBF = 1 bloc (1 polygone). **Table chantiers/SI + géométrie = PLUS TARD.** Pour l'instant tout au niveau UE.
- **Écriture en base UE** (`ue_service.commit_batch`) : regroupe par `unite_d_echantillonnage_ue`, **SOMME `ha_prescription`**, première valeur non-nulle des champs auto, **DÉRIVE `traitement`** depuis `code_dica` (via dica_codes), upsert `ue`. Champs manuels restent nuls (saisie web). Testé : 5.42+1.85→7.27, PL_U-MONO→REB. ✓
- **Convention DATA_MANUELLE** : 🟧 orange=requis, 🟨 jaune=conditionnel(traitement/région), ⬜ gris=dérivé. Requis base : ue, region, rayon, gradient_intensite, code_dica. Conditionnels : plant_ha (REB/REG), denombrement_cn (region=CN & traitement contient AVT), traitement_ps (DEBL/SCA), taux_occ_andain (region=ABIT & DEG/NET/EPC).
- **Pack-driven par year_suffix** : field_definitions et validation_rules scopés par année. Pour une nouvelle année → dupliquer les lignes avec le nouveau year_suffix.

## 6. Sécurité

- JWT (pyjwt HS256) + bcrypt (direct, **passlib abandonné** car incompatible bcrypt 5.0).
- user_ref1 vient TOUJOURS du token (`get_active_user_ref1`), jamais de la requête. Présent dans toutes les tables de données.
- Sessions serveur (idle/absolu/révocation) + anti-brute-force login.
- **RLS PostgreSQL = DÉFÉRÉE à la fin** (une fois le schéma stabilisé). Filtrage actuel = applicatif. Le moment venu : SET app.user_ref1 par requête + ENABLE **+FORCE** RLS (chlorofile2_app est owner) + policies + ajouter user_ref1 à import_batch_rows.

## 7. Reste à faire

1. Tester l'import UE de bout en bout via Swagger (upload UE → commit → GET /ue).
2. Modèles SQLAlchemy `field_definitions`/`list_options` (utiles pour validation + UI ; pas requis pour l'écriture).
3. Service de **validation** (évalue validation_rules + champs requis manquants ; tourne dès le preview pour l'UI).
4. **Édition UE** (PATCH /ue/{uuid}) + edit_history.
5. **Import PDS** (parcelles) — commit renvoie 501 pour l'instant.
6. **Frontend React** (2 vues : import/staging éditable avec champs manquants + bouton Save=push DB+Kizeo ; liste complète éditable).
7. **Géométrie / PostGIS** (PAS dispo sur le serveur actuellement — besoin install admin DB). Importer les .shp, table blocs avec geom.
8. **Génération listes Kizeo** (simulée d'abord).
9. **RLS** (à la toute fin).

## 8. Pièges connus

- Swagger met un placeholder UUID `3fa85f64-...` dans les champs uuid → toujours coller le **vrai** batch_uuid/ue_uuid.
- Swagger préremplit les corps PATCH/POST avec `"string"` → ne garder que les champs voulus.
- Après changement d'alias, **re-uploader** (le staging garde l'ancien mapping).
- `gen_random_uuid()` natif PG13+ (OK sur chlorofile2).

## 9. Préférences du user (important)

- Tester AVANT de committer (git). Ne pas enchaîner du code non testé.
- Archiver/déplacer plutôt que supprimer ; confirmer avant réorg de fichiers.
- Éviter le mot « commit » pour l'écriture en base (confusion git) → dire « écriture en base ».
- Valider le modèle de données avant de coder ; corriger un brouillon plutôt que partir de zéro.
