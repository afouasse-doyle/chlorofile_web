# Notes Frontend — Chlorofile Web (complet)

> À lire avant de bâtir le frontend React. Spécification UI exhaustive : concept d'année,
> rendu piloté par métadonnées, catalogue des champs et des listes, logique conditionnelle,
> écrans, référence API. Complète `ETAT_PROJET.md`. Mise à jour : 2026-06-02.

---

## 0. Stack & démarrage

- **React + TypeScript + Material UI (MUI)**. Dev sur **http://localhost:5173** (Vite) = origine CORS autorisée (`web_allowed_origins`, `backend/app/config.py`). Autre port → l'ajouter côté backend.
- API REST sur `http://localhost:8000`. Swagger `/docs`.
- Libs suggérées : `@tanstack/react-query` (cache + appels API), un form lib (`react-hook-form`) piloté dynamiquement, `axios` avec intercepteur Bearer + refresh-on-401, `dayjs` pour les dates.

---

## 1. ⭐ CONCEPT CENTRAL #1 — L'ANNÉE (`year_suffix` / campagne)

Tout le système est **pack-driven par année**. Une année = `year_suffix` au format `AAAA-AAAA` (ex. `2026-2027`). L'année change **quels champs existent, lesquels sont requis, et les règles** (via `field_definitions` et `validation_rules`, dupliqués par année).

**Implications UI :**
- Un **sélecteur d'année global** (en haut, dans un `YearContext`) = « la campagne active ». Tout en découle.
- L'année choisie détermine : le **form-schema** chargé (champs + obligations), le filtre des UE listées, le `year_suffix` envoyé à l'import.
- Changer d'année recharge le schéma et la liste.
- **Source des années disponibles** : aujourd'hui = `SELECT DISTINCT year_suffix FROM appweb.field_definitions` (les packs configurés). ⚠️ **Pas encore d'endpoint** `GET /years` → à créer (voir §12). En attendant, seule `2026-2027` existe.
- Une UE appartient à une année (`ue.year_suffix`). On ne mélange pas les années dans une vue.

---

## 2. ⭐ CONCEPT CENTRAL #2 — RENDU PILOTÉ PAR LES MÉTADONNÉES

**Ne JAMAIS coder les champs en dur.** Le formulaire UE se génère depuis `field_definitions` (filtré par `entity='ue'` + `year_suffix`). Chaque champ porte :

| Métadonnée | Effet UI |
|---|---|
| `data_type` | widget (voir table §3) |
| `list_name` | si `liste` : source des options (§5) |
| `requirement` | `R`=requis toujours · `C`=conditionnel · `O`=optionnel |
| `validation_rule` | si `C` : nom de la règle qui le rend requis (§6) |
| `min_value`/`max_value` | bornes du champ numérique |
| `is_editable` | `false` → lecture seule (ex. `traitement`, clé UE) |
| `source` | `auto`(DBF) · `manuel`(saisie) · `derive`(calculé) — pour grouper/colorer |
| `display_order` | ordre |
| `label` | libellé |

**Mapping `data_type` → widget MUI :**
| data_type | Widget |
|---|---|
| `texte` | `TextField` |
| `entier` | `TextField type=number` (pas de décimale, step 1) |
| `decimal` | `TextField type=number` (décimales) |
| `date` | `DatePicker` (ISO `YYYY-MM-DD`) |
| `liste` | `Select` ou `Autocomplete` (si longue liste) |
| `booleen` | `Switch`/`Checkbox` |

**Couleurs (convention DATA_MANUELLE à refléter) :** 🟧 requis · 🟨 conditionnel · ⬜ dérivé (lecture seule).

---

## 3. CATALOGUE COMPLET DES CHAMPS UE (38 champs)

`source`: A=auto(DBF) · M=manuel · D=dérivé. `req`: R/O/C.

### 🟧 Requis (R)
| Champ | Label | Type | src | Liste / bornes |
|---|---|---|---|---|
| `unite_d_echantillonnage_ue` | UE | texte | A | clé, lecture seule |
| `region` | Région | liste | M | `region` |
| `rayon` | Rayon | decimal | M | 0–12 |
| `gradient_intensite` | Gradient d'intensité | liste | M | `gradient_intensite` |
| `code_dica` | Code DICA | liste | **A** | `dica_codes` (→ dérive traitement) |

> ⚠️ **`code_dica` est un cas spécial : `source = auto` (vient du DBF `TY_TRAIT`) MAIS requis ET éditable.**
> Il est pré-rempli à l'import. Le front l'affiche comme un champ éditable (Autocomplete sur `dica_codes`)
> pour permettre une correction, mais il n'est pas « vide à saisir » comme les autres requis (region, rayon…).
> Si jamais absent, l'UI propose la liste `dica_codes`. (Corrigé le 2026-06-02 : était `manuel` à tort.)

### ⬜ Dérivé (lecture seule)
| `traitement` | Traitement | texte | D | calculé depuis code_dica |

### 🟨 Conditionnel (C — requis selon traitement/région, voir §6)
| Champ | Label | Type | Bornes | Requis si |
|---|---|---|---|---|
| `plant_ha` | Plant/ha | entier | 600–2000 | traitement ∈ {REB, REG} |
| `traitement_ps` | Préparation de terrain | liste(`traitement_ps`) | — | traitement ∈ {DEBL, SCA} |
| `denombrement_cn` | Dénombrement CN | entier | 0–1000 | region=CN ET traitement contient « AVT » |
| `taux_occ_andain` | Taux occ. andain | entier | 0–100 | region=ABIT ET traitement ∈ {DEG, NET, EPC} |

### 🟦 Auto (du DBF, optionnels)
| Champ | Label | Type | Liste |
|---|---|---|---|
| `no_prescription` | N° prescription | texte | |
| `secteur_intervention` | Secteur d'intervention | texte | |
| `chantier` | Chantier | texte | |
| `uaf` | UAF | texte | |
| `code_ratf` | Code RATF | liste | `code_ratf` (269) |
| `contrat` | Contrat | texte | |
| `projet` | Projet | texte | |
| `ha_prescription` | Superficie (ha) | decimal | somme des blocs |
| `entrepreneur_travaux` | Entrepreneur | texte | |
| `debut` | Date début | date | |
| `fin` | Date fin | date | |

### ⚪ Optionnels manuels
| Champ | Label | Type | Liste/bornes |
|---|---|---|---|
| `nb_parcelle_ue` | Nb parcelles UE | entier | |
| `parcelle_faite` | Parcelle faite | liste | `parcelle_faite` (Oui) |
| `directive_op` | Directive OP | texte | |
| `ha_net` | Superficie nette (ha) | decimal | |
| `origine` | Origine | texte | |
| `preparation_de_terrain` | Préparation terrain (txt) | texte | |
| `type_de_degagement` | Type de dégagement | texte | |
| `equip_utilise` | Équipement utilisé | liste | `equip_utilise` |
| `methode_andains` | Méthode andains | liste | `methode_andains` |
| `nb_si_reboisement` | Nb SI reboisement | entier | 0–10 |
| `plant_max` | Plant max | decimal | |
| `plant_reboise` | Plant reboisé | decimal | |
| `ms_propice` | MS propice | decimal | |
| `note_1` | Note | texte | |
| `andain` | Andain | decimal | |
| `entre_andain` | Entre-andain | decimal | |
| `stocking_av_tr` | Stocking avant traitement | decimal | |

---

## 4. CATALOGUE COMPLET DES LISTES DÉROULANTES

Source = `list_options` (filtrer `list_name` + `region IN ('*', region_UE)`), SAUF `code_dica` (= `dica_codes`).

| list_name | Valeurs | Nb | Notes |
|---|---|---|---|
| `region` | ABIT, BSL, GIM, SLSJ, CN, MAU | 6 | **sélecteur clé** — déclenche les conditionnels |
| `gradient_intensite` | De base, Intensif | 2 | |
| `code_dica` | 149 codes (PL_U-MONO, NET_MEC, EPC_SYS…) | 149 | **Autocomplete** (long). Sélection → dérive `traitement` |
| `code_ratf` | 269 codes | 269 | **Autocomplete** (long) |
| `traitement_ps` | Deblaiement, Placeau_BOP, Placeau_SEPM_RA, Placeau_SEPM_RN, SCA_Sillons_pleins_partiels, SCA_Sillons_Sentiers, SCA_Sillons_Zipper | 7 | |
| `equip_utilise` | Pelle, Bouteur, Débusqueuse, Transporteur | 4 | |
| `methode_andains` | Drone, Terrain | 2 | |
| `parcelle_faite` | Oui | 1 | (case à cocher de fait) |

**Méta-listes** (pour un éventuel écran d'admin de `field_definitions`) : `requirement` (R/O/C), `data_type`, `field_source` (auto/manuel/derive), `entity` (ue/parcelle).

**Scoping par région :** `list_options.region` vaut `'*'` (toutes) ou une région. Aujourd'hui tout est `'*'`. Le front doit quand même filtrer `region IN ('*', region_de_l_UE)` pour être prêt si une liste devient régionale.

---

## 5. LA DÉRIVATION `code_dica → traitement` (à montrer en direct)

- `code_dica` est saisi (Autocomplete sur 149 codes). `traitement` en est **dérivé** via `dica_codes` (ex. `PL_U-MONO→REB`, `NET_MEC→NET`, `EPC_SYS→EPC`, `PL_REG-MONO→REG`, `DEG_AVT→DEG_AVT`).
- Côté UI : afficher `traitement` en **lecture seule** à côté de `code_dica`, mis à jour dès qu'on change `code_dica`. La dérivation est aussi faite côté backend au PATCH (la réponse renvoie l'UE avec le nouveau `traitement`).
- ⚠️ `traitement` n'est PAS le code dica : c'est le code court (REB, NET, DEG_AVT…) qui pilote les conditionnels.

---

## 6. LOGIQUE CONDITIONNELLE / CASCADE (cœur de la saisie)

Les champs 🟨 deviennent **requis** selon `(year_suffix, region, traitement)`. Règles (table `validation_rules`, `traitement_match` = `in`/`contains`/`exact`) :

| Règle | Champ requis | Condition |
|---|---|---|
| `plant_ha_plantation` | `plant_ha` | traitement `in` (REB, REG) |
| `traitement_ps_prep` | `traitement_ps` | traitement `in` (DEBL, SCA) |
| `denombrement_cn_avt` | `denombrement_cn` | region=CN ET traitement `contains` AVT |
| `taux_occ_andain_abit` | `taux_occ_andain` | region=ABIT ET traitement `in` (DEG, NET, EPC) |

**Effet cascade :** choisir `code_dica` (→ traitement) ou `region` peut **activer** de nouveaux champs requis. Deux stratégies front :
1. **Simple** : après chaque modif, appeler `GET /ue/{uuid}/validation` → re-afficher les manquants + le statut. (Backend = source de vérité.)
2. **Réactif** : récupérer les `rules` via le form-schema (§12) et évaluer côté client pour marquer les ★ en direct, + confirmer au backend. Le `traitement_match` `contains` = `traitement.includes('AVT')`, `in` = `liste.includes(traitement)`.

---

## 7. LE « JUGE » DE VALIDATION (statuts)

- `GET /ue/{uuid}/validation` → `{ ue_uuid, statut, is_valid, missing: [{field_name, label, requirement, message}] }`.
- « Requis » = **présence** (non-null). L'appartenance d'une valeur à sa liste est garantie par le dropdown (pas re-vérifiée).
- **Statuts** (`ue.statut_validation`) : `non_valide` (rien/incomplet jamais édité) → `en_cours` (édité, incomplet) → `valide` (tous requis remplis). Le PATCH recalcule et pose le statut. Badges : rouge / orange / vert.
- Le même juge garde **3 portes** : édition web (statut), gate import PDS (refuse parcelles si UE non valide), gate Kizeo (à venir).

---

## 8. LES ÉCRANS (menu gauche)

### Login
Form email + mot de passe → stocke le JWT → redirige. Sur 401 ailleurs → revient ici.

### Dashboard
Compteurs : UE par statut (non_valide/en_cours/valide), nb imports récents, etc. (Endpoint à créer.)

### Import DBF
1. Formulaire : choisir fichier `.dbf`, `dbf_type` (UE/PDS), année (du contexte). → `POST /imports/upload`.
2. Afficher l'**aperçu** : `mapped_fields` (reconnus), `unmapped_fields` (ignorés), `missing_targets`, table `preview_rows`. Badge `can_commit`.
3. Bouton **Commit** → `POST /imports/{batch_uuid}/commit`. UE → crée/maj les UE. (⚠️ utiliser le **vrai** `batch_uuid` renvoyé, pas le placeholder Swagger.)
4. Idéalement enchaîner sur la **vue staging** : tableau des UE créées, statut, champs manquants, clic → édition.

#### ⭐ Détection de conflits au ré-import UE (conçu, backend pas encore codé)

Quand on ré-importe un DBF UE par-dessus des données existantes, il faut **protéger le travail manuel**. Comportement à implémenter (front + endpoint backend de comparaison, voir §12) :

- **Règle d'or NON-DESTRUCTIVE** : un champ vide dans le DBF n'écrase **jamais** une valeur en base. Les champs **manuels** (region, rayon, gradient_intensite, plant_ha…) ne sont jamais touchés par un import — la saisie web est sacrée.
- Le preview classe chaque ligne : 🟢 **nouvelle UE** (création) · ⚪ **existante identique** (no-op) · 🟠 **existante avec champ auto différent** (conflit).
- Conflit champ auto → afficher **ancienne (base) vs nouvelle (DBF)**, **défaut = garder la base**, décision **par conflit** dans l'UI. **Jamais d'écrasement silencieux.**
- ⚠️ **État actuel du backend** : `ue_service.commit_batch` écrase aujourd'hui les champs auto sans demander, et peut même remettre à `None` un champ absent du DBF (dont `region`, qui est listé dans `_UE_FIRST_FIELDS`). **À durcir avant d'ouvrir le ré-import aux utilisateurs** (voir Phase 4A du roadmap) — sinon un ré-import accidentel efface la saisie.

### UE (liste)
Table filtrable (par année du contexte, statut, traitement, region…). Colonnes typiques : UE, traitement, region, ha_prescription, statut (badge), nb champs manquants. Clic → détail/édition. Source : `GET /ue/?year_suffix=`.

### UE (détail / édition) — **l'écran le plus important**
- Formulaire **généré dynamiquement** (form-schema). Grouper par section : *Identité (auto)*, *Prescription (auto)*, *Saisie requise*, *Conditionnels actifs*, *Optionnels*.
- Champs `is_editable=false` (UE, traitement, champs auto) en lecture seule (ou auto mais éditables si tu veux corriger — voir `is_editable`).
- Marqueurs ★ requis (R + C activés). Validation des bornes (min/max) côté client + backend (422).
- `code_dica` → met à jour `traitement` affiché en direct → ré-évalue les conditionnels.
- Sauvegarde → `PATCH /ue/{uuid}` `{fields:{...}}` → réponse `{ue, validation}` → rafraîchir manquants + statut.

### Parcelles
Liste des parcelles d'une UE (issues de l'import PDS). `GET /parcelles?ue_uuid=` (**à créer**).
- **Gate** : les parcelles ne s'attachent qu'aux UE **valides** (`is_valid`). Un import PDS sur une UE incomplète est ignoré (compteur `parcelle_skipped_ue_incomplete`).
- **Wipe / remplacement** : ré-importer un plan de sondage **remplace** les parcelles de l'UE (celles absentes du nouveau lot → soft-delete `is_active=false`), **scopé à l'UE du lot uniquement** — les parcelles des autres UE ne bougent jamais.
- Affichage : par défaut seules les actives ; prévoir un toggle `include_inactive` (les archivées restent en base, récupérables).

### Validation
Vue transversale : toutes les UE avec leur statut + manquants, pour piloter la complétude avant génération Kizeo.

### Génération Kizeo
Bouton « Générer liste Kizeo » pour les UE valides. Simulé d'abord (endpoint à créer).

### Administration (fqcf_admin only)
Gestion des comptes : `GET/POST/PATCH /auth/users`. Masquer ce menu si `role != fqcf_admin`.

---

## 9. ARCHITECTURE FRONT SUGGÉRÉE

- **AuthContext** : token + user (`/auth/me`), login/logout, garde de route. Intercepteur axios : ajoute `Bearer`, gère 401 → logout.
- **YearContext** : année active (liste via `/years` futur), partagée partout.
- **react-query** : `useQuery` pour form-schema/listes/UE (cache), `useMutation` pour upload/commit/patch.
- **Form dynamique** : un composant `DynamicField` qui rend le bon widget selon `data_type` + `list_name`, et un `UeForm` qui mappe le form-schema. Gérer required (R + C calculés) et bornes.
- **Rôles** : masquer/afficher selon `role` ; le backend renvoie 403 de toute façon.

---

## 10. RÉFÉRENCE API (pour le front)

### Auth
- `POST /auth/login` — **form-urlencoded** (PAS JSON) : `username`=email, `password`. → `{access_token, token_type:"bearer"}`.
- `GET /auth/me` → `{user_uuid, email, full_name, user_ref1, role, is_active, last_login_at}`.
- `POST /auth/logout` → 204.
- `GET /auth/users` (fqcf_admin), `POST /auth/users` (`{email,password,full_name,user_ref1,role}`), `PATCH /auth/users/{user_uuid}`.

### Import
- `POST /imports/upload` — **multipart** : `file`, `dbf_type`(UE|PDS), `year_suffix`. → `{batch_uuid, dbf_type, original_filename, total_rows, raw_fields[], mapped_fields{}, unmapped_fields[], missing_targets[], preview_rows[], ue_key_present, can_commit}`.
- `POST /imports/{batch_uuid}/commit` →
  - UE : `{batch_uuid, status:"committed", ue_created, ue_updated, ue_total}`
  - PDS : `{batch_uuid, status:"committed", parcelle_created, parcelle_updated, parcelle_deactivated, parcelle_skipped_invalide, parcelle_skipped_ue_absente, parcelle_skipped_ue_incomplete, ue_touched}`
- `GET /imports/` → liste des lots.

### UE
- `GET /ue/?year_suffix=&include_inactive=` → `UeOut[]`.
- `GET /ue/{ue_uuid}` → `UeOut` (les ~30 champs principaux).
- `GET /ue/{ue_uuid}/validation` → `{ue_uuid, statut, is_valid, missing:[{field_name,label,requirement,message}]}`.
- `PATCH /ue/{ue_uuid}` — body `{ "fields": { "<champ>": <valeur>, ... } }` (champs éditables seulement) → `{ue: UeOut, validation: {...}}`. **422** si borne ou champ non éditable.

---

## 11. GESTION DES ERREURS (codes à gérer)

| Code | Sens | Action UI |
|---|---|---|
| 401 | token invalide/expiré | logout → login |
| 403 | pas le rôle (ex. non admin) | message « accès refusé » |
| 404 | introuvable (UE, lot…) | message + retour liste |
| 409 | conflit (ex. commit d'un lot pas en preview) | message |
| 422 | validation (borne min/max, champ inconnu, role invalide) | erreur inline sur le champ (`detail`) |
| 429 | trop de tentatives login | « réessayez plus tard » + Retry-After |
| 501 | non implémenté (ex. PDS dans certains cas) | message « à venir » |

⚠️ Pièges : login = form-urlencoded ; ne jamais envoyer `user_ref1` (vient du token) ; Swagger met un placeholder UUID `3fa85f64-…` qu'il ne faut pas réutiliser ; décimaux en string Decimal ; dates ISO.

---

## 12. À CONSTRUIRE CÔTÉ BACKEND **AVANT** LE FRONT (TODO prioritaire)

1. **`GET /ue/form-schema?year_suffix=YYYY-YYYY`** (priorité #1) — renvoie tout ce qu'il faut pour générer le formulaire en un seul appel. Source : `field_definitions` (filtré `entity='ue'`, année, `is_active`) + `list_options`/`dica_codes` résolues + `validation_rules` actives.
   ```jsonc
   {
     "year_suffix": "2026-2027",
     "fields": [ { "field_name","label","data_type","source","requirement",
                   "list_name","validation_rule","min_value","max_value",
                   "is_editable","display_order" } ],   // triés par display_order
     "lists":  { "region": [{"value","label"}], "code_dica":[...], ... },  // options résolues, code_dica depuis dica_codes
     "rules":  [ { "rule_name","champ","region","traitement","traitement_match" } ] // pour les ★ réactifs (§6)
   }
   ```
   Le modèle `FieldDefinition` existe déjà (`backend/app/models/field_definition.py`). Manque : le modèle `ListOption` + le routeur. Réutiliser la même logique de dédup que le juge (année précise > `'*'`).
2. **`GET /years`** — années disponibles (`DISTINCT year_suffix` de field_definitions). En attendant, seule `2026-2027` existe.
3. **`GET /parcelles?ue_uuid=&include_inactive=`** — parcelles d'une UE (scopé coop). Modèle `Parcelle` déjà en place.
4. **Endpoint génération Kizeo** (simulé d'abord) — réutilise le juge comme **pré-vol** : ne pousse que les UE `is_valid`, et **retourne la liste des UE bloquées + leurs champs manquants** avant tout envoi. Écrit `kizeo_generation_log`.
5. **Endpoint Dashboard** (compteurs par statut : non_valide/en_cours/valide + imports récents).
6. **Endpoint de comparaison de conflits au ré-import UE** (voir §8) — compare un lot stagé aux UE en base et retourne le classement 🟢/⚪/🟠 par UE + les écarts de champs auto. **Couplé** au durcissement non-destructif de `ue_service.commit_batch` (ne jamais écraser avec une valeur vide ; sortir `region` de `_UE_FIRST_FIELDS` puisque c'est un champ manuel).

Sans le #1, le front ne peut pas générer les formulaires dynamiquement — c'est le **premier chantier backend** quand on passera au frontend. Le #6 est à faire **avant** d'autoriser les ré-imports en usage réel (protège la saisie manuelle).
