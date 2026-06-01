# Architecture — Chlorofile Web Portal

## Contexte et périmètre

Chlorofile Web est un produit **totalement indépendant** du système Flask existant (`C:\srv\flaskapp`). Il remplace progressivement les fichiers DATA_MANUELLE et les macros VBA. Le système Flask continue d'exister sans modification.

```
Système existant (inchangé)           Nouveau produit
────────────────────────────          ─────────────────────────────
Kizeo → Make → Flask                  Navigateur
→ Scripts Python                       → Caddy (reverse proxy)
→ PostgreSQL schema app/form_id        → FastAPI (port 8000)
→ SharePoint                           → PostgreSQL schema appweb
```

Les deux systèmes partagent la même base PostgreSQL `chlorofile2` mais dans des **schémas strictement séparés** : `app` (existant) et `appweb` (nouveau). Le portail ne lit jamais dans `app` pour l'instant.

---

## Décisions d'architecture (ADR)

### ADR-1 : FastAPI plutôt que Flask

**Décision** : FastAPI pour le backend.

**Raison** : Le portail expose une vraie API REST consommée par un frontend React — FastAPI génère OpenAPI/Swagger automatiquement, force la validation via Pydantic v2 dès la signature de fonction, et gère les opérations async (futur) nativement. Flask (système existant) reste pour le dispatcher Make.

### ADR-2 : Schéma `appweb` séparé, jamais `app`

**Décision** : Toutes les tables du portail dans le schéma `appweb`. Aucune écriture dans `app`.

**Raison** : Isolation complète. Si le portail plante ou est mal configuré, le pipeline opérationnel (`app`) ne peut pas être corrompu. Une lecture en `app` pourra être ajoutée plus tard en lecture seule et au besoin.

### ADR-3 : Suppressions logiques uniquement

**Décision** : Jamais de `DELETE` physique. `is_active = false` ou `deleted_at IS NOT NULL`.

**Raison** : Cohérence avec le système Flask existant, auditabilité, possibilité de rejouer un import.

### ADR-4 : `field_aliases` pilote le mapping DBF

**Décision** : La table `appweb.field_aliases` mappe les noms DBF bruts vers les noms canoniques. Le code ne contient aucun mapping hardcodé.

**Raison** : Les DBF varient selon les années et les producteurs. Ajouter un nouveau format = un INSERT en base, pas une modification de code.

### ADR-5 : Import en deux étapes — preview puis commit

**Décision** : L'import DBF produit d'abord un aperçu normalisé (sans écriture en base). L'utilisateur valide, puis confirme le commit.

**Raison** : Évite les imports accidentels. Permet à l'utilisateur de voir exactement ce qui sera écrit avant de s'engager. La session d'import passe par les états `pending → preview → committed`.

### ADR-6 : Alembic pour les migrations

**Décision** : Toutes les migrations de schéma passent par Alembic.

**Raison** : Traçabilité complète de l'évolution du schéma, rollback possible, pas de DDL ad-hoc.

### ADR-7 : Validation configurable en base, pas en code

**Décision** : `appweb.validation_rules` contient les règles par année/module/traitement. Le code de validation est générique.

**Raison** : Les champs obligatoires changent d'une année à l'autre. Modifier une règle = un UPDATE en base, pas un redéploiement.

---

## Arborescence du projet

```
C:\srv\chlorofile_web\
│
├── backend/
│   ├── app/
│   │   ├── main.py                  # Point d'entrée FastAPI
│   │   ├── config.py                # Settings via pydantic-settings (chargé depuis .env)
│   │   ├── database.py              # Engine SQLAlchemy + Session factory
│   │   ├── dependencies.py          # Dépendances FastAPI partagées (get_db, auth)
│   │   │
│   │   ├── models/                  # Modèles SQLAlchemy (ORM)
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # Base déclarative + TimestampMixin
│   │   │   ├── field_alias.py       # appweb.field_aliases
│   │   │   ├── import_session.py    # appweb.import_sessions
│   │   │   ├── ue.py                # appweb.unite_echantillonnage
│   │   │   ├── parcelle.py          # appweb.parcelles
│   │   │   ├── edit_history.py      # appweb.edit_history
│   │   │   ├── validation_rule.py   # appweb.validation_rules
│   │   │   ├── validation_result.py # appweb.validation_results
│   │   │   └── kizeo_log.py         # appweb.kizeo_generation_log
│   │   │
│   │   ├── schemas/                 # Schémas Pydantic v2 (request / response)
│   │   │   ├── __init__.py
│   │   │   ├── import_session.py    # ImportSessionCreate, ImportSessionOut, DBFPreview
│   │   │   ├── ue.py                # UEOut, UEUpdate, UEListOut
│   │   │   ├── parcelle.py          # ParcelleOut, ParcelleUpdate
│   │   │   └── validation.py        # ValidationRuleOut, ValidationResultOut
│   │   │
│   │   ├── routers/                 # Routeurs FastAPI (1 fichier = 1 domaine)
│   │   │   ├── __init__.py
│   │   │   ├── imports.py           # POST /imports/upload, POST /imports/{id}/commit
│   │   │   ├── ue.py                # GET/PATCH /ue, GET /ue/{id}
│   │   │   ├── parcelles.py         # GET/PATCH /parcelles
│   │   │   ├── validation.py        # POST /validation/run, GET /validation/rules
│   │   │   └── kizeo.py             # POST /kizeo/generate/{ue_id}
│   │   │
│   │   └── services/                # Logique métier pure (pas de FastAPI ici)
│   │       ├── __init__.py
│   │       ├── dbf_import.py        # Lecture DBF + normalisation (livraison #1)
│   │       ├── ue_service.py        # Génération UE depuis prescriptions importées
│   │       ├── parcelle_service.py  # Upsert parcelles depuis PDS importées
│   │       ├── validation_service.py # Évaluation des validation_rules
│   │       └── kizeo_service.py     # Préparation du payload Kizeo (simulation)
│   │
│   ├── migrations/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 0001_create_appweb_schema.py
│   │
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_dbf_import.py       # Tests du service d'import (priorité 1)
│   │   ├── test_validation.py
│   │   └── fixtures/
│   │       └── sample.dbf           # Fichier DBF de test
│   │
│   ├── requirements.txt
│   └── alembic.ini
│
├── frontend/                        # React + TypeScript + Material UI (phase 2)
│
├── logs/
│   └── chlorofile_web.log
│
├── docs/
│   └── chlorofile_web/
│       ├── architecture.md          # Ce fichier
│       └── schema_appweb.sql        # DDL complet du schéma appweb
│
├── .venv/
├── CLAUDE.md
└── .gitignore
```

---

## Flux d'import DBF (Fonctionnalité #1)

```
Utilisateur
    │  POST /imports/upload  (fichier DBF + dbf_type + year_suffix)
    ▼
ImportRouter
    │  crée ImportSession (status=pending)
    │  appelle DBFImportService.preview()
    ▼
DBFImportService.preview()
    │  lit le fichier DBF avec dbfread
    │  détecte les champs présents
    │  charge field_aliases pour ce dbf_type
    │  applique le mapping → dict canonique par ligne
    │  retourne DBFPreview (colonnes détectées, colonnes manquantes, aperçu 10 lignes)
    │  met à jour ImportSession (status=preview)
    ▼
API → réponse JSON avec aperçu normalisé

Utilisateur valide l'aperçu
    │  POST /imports/{session_uuid}/commit
    ▼
ImportRouter
    │  appelle UEService.upsert_from_preview()  ← si PLR ou RXF
    │  appelle ParcelleService.upsert_from_preview()  ← si PDS
    │  met à jour ImportSession (status=committed)
    ▼
Réponse : nb_ue_created, nb_ue_updated, nb_parcelles_created, etc.
```

---

## Flux de validation (Fonctionnalité #4)

```
POST /validation/run?user_ref1=X&year_suffix=Y
    ▼
ValidationService
    │  charge toutes les UE actives (user_ref1, year_suffix)
    │  charge les validation_rules applicables (year_suffix + traitement)
    │  pour chaque UE : évalue chaque règle
    │  pour chaque parcelle de l'UE : évalue les règles parcelle
    │  écrit les ValidationResults (run_uuid commun)
    │  met à jour statut_validation sur chaque UE
    ▼
Réponse : résumé par UE (nb_erreurs, champs_invalides)
```

---

## Variables d'environnement — portail uniquement

À ajouter dans le `.env` existant (hors dépôt Git) :

| Variable              | Description                                              |
| --------------------- | -------------------------------------------------------- |
| `WEB_PG_USER`         | Utilisateur PostgreSQL dédié au portail (lecture/écriture sur `appweb`) |
| `WEB_PG_PASS`         | Mot de passe de cet utilisateur                          |
| `WEB_SECRET_KEY`      | Clé de signature JWT (sessions portail)                  |
| `WEB_ALLOWED_ORIGINS` | CORS — origines autorisées (ex: `https://chlorofile.fqcf.coop`) |

`PG_HOST`, `PG_PORT`, `PG_DB` sont partagés avec le système Flask (même serveur, même base).

---

## Dépendances Python (backend)

```
fastapi>=0.115
uvicorn[standard]>=0.30        # ou waitress sur Windows
sqlalchemy>=2.0
alembic>=1.13
pydantic>=2.7
pydantic-settings>=2.3
psycopg2-binary>=2.9
dbfread>=2.0.7                 # lecture de fichiers DBF
python-multipart>=0.0.9        # upload fichiers FastAPI
```

---

## Voir aussi

- [schema_appweb.sql](schema_appweb.sql) — DDL complet du schéma appweb
- [../postgresql_schema.md](../postgresql_schema.md) — schéma `app` existant (ne pas modifier)
- [../vision.md](../vision.md) — direction stratégique du projet
