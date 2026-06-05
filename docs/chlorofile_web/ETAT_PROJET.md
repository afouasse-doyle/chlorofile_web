# État du projet — Chlorofile Web (handoff)

> Document de reprise. À lire en premier dans une nouvelle session pour comprendre où on en est sans tout réexpliquer. Dernière mise à jour : 2026-06-02.

---

## 1. Objectif

Portail web **indépendant** du système Flask existant (`C:\srv\flaskapp`), qui remplace les fichiers Excel `DATA_MANUELLE` et les macros VBA. Permet aux coops d'importer leurs DBF (prescriptions / parcelles), compléter les champs manquants, valider, et générer les listes Kizeo — **sans ouvrir DATA_MANUELLE**.

- Le portail = source de vérité. Excel devient une *sortie*, plus une source.
- Ne **jamais** toucher au schéma `app` ni au système flaskapp (référence seulement, copiée dans ce dossier).

## 2. Stack & emplacements

- Backend : **FastAPI + SQLAlchemy 2.0 + Pydantic v2 + psycopg2**, Python **3.13.7** (venv `.venv`)
- DB : PostgreSQL `chlorofile2`, schéma **`appweb`** (isolé de `app`). Hôte `159.203.59.12`, user `chlorofile2_app` (= `WEB_PG_USER`).
- `.env` partagé via `CHLOROFILE_ENV_PATH` . Vars portail : `WEB_PG_USER`, `WEB_PG_PASS`, `WEB_SECRET_KEY` (≥32o).
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
| `list_options` | menus déroulants génériques | 305 valeurs (région, traitement_ps, code_ratf, equip_utilise… + méta-listes). Seed depuis validations Excel. **Modèle SQLAlchemy pas encore fait** (le juge n'en a pas besoin) |
| `field_definitions` | catalogue de champs | 38 champs UE. data_type/source/requirement(R/O/C)/list_name/validation_rule/min/max. **Pack-driven par year_suffix**. Modèle `FieldDefinition` ✅. NB : `code_dica` = `source='auto'` (vient du DBF TY_TRAIT, pas saisi) |
| `validation_rules` | règles conditionnelles | keyé (year_suffix, region, traitement, traitement_match). 4 règles nommées. Modèle complété (`rule_name`, `region`, `traitement_match`) ✅ |
| `import_batches` | lots d'import | pending→preview→committed. dbf_type UE/PDS |
| `import_batch_rows` | lignes stagées | raw_data + normalized_data (JSONB) |
| `ue` | **entité principale** | 47 colonnes (alignée sur app.prescriptions). user_ref1, year_suffix |
| `parcelles` | parcelles (PDS) | **alimentée ✅** (import PDS + wipe scopé par UE, soft-delete) |
| `edit_history` | audit des saisies | **utilisée ✅** par PATCH /ue (1 ligne par champ changé) |
| `validation_results`, `kizeo_generation_log` | audit/log | prêtes, pas encore utilisées |

Seeds versionnés : `dica_codes_seed.sql`, `list_options_seed.sql`, `field_definitions_seed.sql`, `validation_rules_seed.sql`. `schema_appweb.sql` = DDL canonique synchronisé et validé (idempotent).

## 4. Endpoints API (fonctionnels)

- **Auth** : `POST /auth/login` (email+mdp→JWT), `POST /auth/logout`, `GET /auth/me`, `GET/POST/PATCH /auth/users` (fqcf_admin only)
- **Import** : `POST /imports/upload` (DBF→preview+staging), `POST /imports/{batch_uuid}/commit` (UE→écriture base ; **PDS→parcelles avec gate « UE valide »**), `GET /imports/`
- **UE** : `GET /ue/`, `GET /ue/{ue_uuid}`, **`GET /ue/{ue_uuid}/validation`** (juge : champs manquants + statut), **`PATCH /ue/{ue_uuid}`** (édition : bornes min/max, audit, re-dérivation traitement, recalcul statut)
- Création de comptes = **fqcf_admin only** (pas d'auto-inscription). CLI `backend/scripts/create_user.py` pour le 1er admin. `hash_password.py` pour un INSERT manuel.

## 5. Modèle métier UE (validé avec le user)

- **DBF type = UE ou PDS** (pas PLR/RXF — ce sont tous des UE ; variations régionales absorbées par les alias).
- 1 UE = 1..n chantiers/secteurs d'intervention ; chaque ligne DBF = 1 bloc (1 polygone). **Table chantiers/SI + géométrie = PLUS TARD.** Pour l'instant tout au niveau UE.
- **Écriture en base UE** (`ue_service.commit_batch`) : regroupe par `unite_d_echantillonnage_ue`, **SOMME `ha_prescription`**, première valeur non-nulle des champs auto, **DÉRIVE `traitement`** depuis `code_dica` (via dica_codes), upsert `ue`. Champs manuels restent nuls (saisie web). Testé : 5.42+1.85→7.27, PL_U-MONO→REB. ✓
- **Convention DATA_MANUELLE** : 🟧 orange=requis, 🟨 jaune=conditionnel(traitement/région), ⬜ gris=dérivé. Requis base : ue, region, rayon, gradient_intensite, code_dica. Conditionnels : plant_ha (REB/REG), denombrement_cn (region=CN & traitement contient AVT), traitement_ps (DEBL/SCA), taux_occ_andain (region=ABIT & DEG/NET/EPC).
- **Pack-driven par year_suffix** : field_definitions et validation_rules scopés par année. Pour une nouvelle année → dupliquer les lignes avec le nouveau year_suffix.

### 5bis. Validation & édition (le « juge » — `services/validation_service.py`)

- **Un seul juge** de complétude d'UE, réutilisé partout (DRY) : `validate_ue(db, ue)` → `{statut, is_valid, missing[]}`. **Pur** (n'écrit rien).
- Contrat : `R` requis toujours · `C` requis seulement si sa règle nommée (`validation_rules.rule_name`) matche `(year_suffix, region, traitement)` via `traitement_match` (`exact`/`in`/`contains`) · `O` ne bloque jamais. « Requis » = **présence** (non-null). L'appartenance d'un champ liste à sa liste est garantie par le frontend (dropdown), **pas** vérifiée par le juge.
- Cascade : saisir `region` peut activer de nouveaux conditionnels → le juge re-tourne à chaque PATCH.
- **3 portes, même juge** : (1) édition web met à jour `statut_validation` · (2) **gate PDS** refuse les parcelles si l'UE n'est pas `is_valid` · (3) gate Kizeo (à venir) ne poussera que les UE valides.
- **Édition** (`services/ue_edit_service.py`, `PATCH /ue/{uuid}`) : seuls les champs `is_editable` ; coercition par `data_type` ; **bornes min/max rejetées en 422** ; `code_dica` modifié → re-dérive `traitement` ; chaque champ changé journalisé dans `edit_history` (changed_by = email) ; statut recalculé → `valide` si complet, sinon `en_cours` (posé par le PATCH, pas déduit par le juge qui ne sort que `valide`/`non_valide`).
- **Import PDS** (`services/pds_service.py`) : 1 ligne = 1 parcelle ; ne s'accroche qu'à une UE existante **ET** `is_valid` ; **wipe scopé par UE** (parcelles absentes du lot → soft-delete `is_active=false`, seulement pour les UE du lot) ; compteurs : `created/updated/deactivated` + skip `invalide`/`ue_absente`/`ue_incomplete`.

## 6. Sécurité

- JWT (pyjwt HS256) + bcrypt (direct, **passlib abandonné** car incompatible bcrypt 5.0).
- user_ref1 vient TOUJOURS du token (`get_active_user_ref1`), jamais de la requête. Présent dans toutes les tables de données.
- Sessions serveur (idle/absolu/révocation) + anti-brute-force login.
- **RLS PostgreSQL = DÉFÉRÉE à la fin** (une fois le schéma stabilisé). Filtrage actuel = applicatif. Le moment venu : SET app.user_ref1 par requête + ENABLE **+FORCE** RLS (chlorofile2_app est owner) + policies + ajouter user_ref1 à import_batch_rows.

## 7. Reste à faire

- ~~Tester l'import UE de bout en bout~~ ✅ fait
- ~~Service de validation (le juge)~~ ✅ fait + testé sur UE-050
- ~~Édition UE (PATCH) + edit_history~~ ✅ fait + testé (bornes, audit, statut)
- ~~Import PDS (parcelles)~~ ✅ fait + testé (gate UE valide, wipe scopé)

Reste :

1. Modèle SQLAlchemy `list_options` (utile UI ; pas requis tant que le frontend n'est pas là). Éventuellement `field_definitions` parcelle en lecture seule pour l'affichage (parcelle = passe-plat, pas de saisie manuelle sauf no_parcelle/no_ue).
2. **Frontend React** — spec UI complète : `FRONTEND_NOTES.md` · plan de sprint ordonné : `ROADMAP_FRONTEND.md` (4A endpoints prérequis → 4B fondations → 4C écrans). **Hébergement prévu : WHC + cPanel** (build statique).
   - **Détection de conflits au ré-import UE** (conçu, pas codé) : le preview doit comparer chaque ligne DBF aux UE en base et signaler 🟢 nouvelle / ⚪ identique / 🟠 conflit (champ auto différent). **Règle d'or non-destructive** : un champ vide dans le DBF n'écrase JAMAIS une valeur en base ; les champs manuels ne sont jamais touchés par un import. Conflit champ auto → **défaut = garder la base**, décision **par conflit** dans l'UI (jamais d'écrasement silencieux).
3. **Génération listes Kizeo** (gate Kizeo = ne pousser que les UE valides, réutilise le juge ; simulée d'abord).
4. **Géométrie / PostGIS** (PAS dispo sur le serveur actuellement — besoin install admin DB). Importer les .shp, table blocs avec geom.
5. **RLS** (à la toute fin).

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
