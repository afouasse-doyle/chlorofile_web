-- =============================================================================
-- Schéma appweb — Chlorofile Web Portal
-- PostgreSQL 15+
-- =============================================================================
-- Convention : toutes les tables ont un id BIGSERIAL pour le tri d'insertion.
-- user_ref1 présent sur toutes les tables coop (RLS-ready).
-- Suppressions toujours logiques (is_active = false).
--
-- IMPORTANT : tout est dans le schéma `appweb`, jamais `app`.
-- Le système Flask existant possède son propre schéma `app` qu'on ne touche pas.
-- Les noms de champs cibles (target_field) sont alignés sur la convention de `app`
-- (unite_d_echantillonnage_ue, numero_de_parcelle, region…) pour faciliter une
-- future couche BI/IA qui interrogerait les deux schémas de façon cohérente.
-- =============================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS appweb;

-- ---------------------------------------------------------------------------
-- 0. Authentification — utilisateurs du portail
-- ---------------------------------------------------------------------------
-- Table de login du portail. Après connexion, l'utilisateur est associé à un
-- user_ref1 (code coop) qui devient la clé de tous les accès aux données.
-- C'est le pont entre l'authentification web et la donnée automatisée Chlorofile.
--
-- SÉCURITÉ : user_ref1 vient TOUJOURS d'ici (le token), jamais de la requête.
--   C'est ce qui rend la RLS fiable côté portail.
--
-- user_ref1 doit correspondre à un app.coops.user_ref1 existant. On ne met PAS
-- de FK cross-schéma (indépendance des deux systèmes) — la cohérence est
-- vérifiée par la couche applicative quand la lecture de app.coops sera activée.
CREATE TABLE IF NOT EXISTS appweb.users (
    id              BIGSERIAL   PRIMARY KEY,
    user_uuid       UUID        NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    email           TEXT        NOT NULL UNIQUE,        -- identifiant de connexion
    password_hash   TEXT        NOT NULL,               -- bcrypt — jamais le mot de passe en clair
    full_name       TEXT,
    user_ref1       TEXT,                               -- coop associée (clé RLS). NULL = admin global FQCF
    role            TEXT        NOT NULL DEFAULT 'coop_user',
    -- 'coop_user'  : utilisateur d'une coop (lecture/écriture sur sa coop)
    -- 'coop_admin' : administrateur d'une coop
    -- 'fqcf_admin' : administrateur global (toutes coops, user_ref1 peut être NULL)
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,  -- soft-delete / désactivation
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT users_role_check
        CHECK (role IN ('coop_user', 'coop_admin', 'fqcf_admin'))
);

COMMENT ON TABLE appweb.users IS
    'Utilisateurs du portail web. La connexion (email + mot de passe) associe '
    'l''utilisateur à un user_ref1 qui pilote tous ses accès aux données. '
    'password_hash = bcrypt. user_ref1 NULL = administrateur global FQCF.';

CREATE INDEX IF NOT EXISTS idx_users_user_ref1 ON appweb.users (user_ref1) WHERE is_active;

-- ---------------------------------------------------------------------------
-- 0bis. Sessions — contrôle d'inactivité, timeout absolu et révocation
-- ---------------------------------------------------------------------------
-- Le JWT seul est sans état : impossible d'imposer un timeout d'inactivité ni
-- de révoquer un token volé. Cette table rend chaque session contrôlable côté
-- serveur. Le JWT ne porte plus qu'un pointeur (session_uuid) ; tout le contrôle
-- de durée de vie se fait ici.
--   - last_seen_at : mis à jour à chaque requête → base du timeout d'inactivité
--   - expires_at   : borne absolue, fixée à la connexion
--   - revoked_at   : déconnexion / révocation immédiate (logout, compte compromis)
CREATE TABLE IF NOT EXISTS appweb.user_sessions (
    id              BIGSERIAL   PRIMARY KEY,
    session_uuid    UUID        NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    user_id         BIGINT      NOT NULL REFERENCES appweb.users(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),   -- début de session
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),   -- dernière activité (inactivité)
    expires_at      TIMESTAMPTZ NOT NULL,                 -- borne absolue (cap dur)
    revoked_at      TIMESTAMPTZ,                          -- logout / révocation
    ip_address      TEXT,                                 -- IP à la connexion (audit)
    user_agent      TEXT                                  -- navigateur (audit)
);

COMMENT ON TABLE appweb.user_sessions IS
    'Sessions actives du portail. Permet le timeout d''inactivité (last_seen_at), '
    'le timeout absolu (expires_at) et la révocation immédiate (revoked_at).';

CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON appweb.user_sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_active
    ON appweb.user_sessions (session_uuid) WHERE revoked_at IS NULL;

-- ---------------------------------------------------------------------------
-- 0ter. Tentatives de connexion — anti-brute-force + audit
-- ---------------------------------------------------------------------------
-- Une ligne par tentative de login (réussie ou non). Le verrouillage est une
-- fenêtre glissante : on compte les échecs récents par email ET par IP. Au-delà
-- d'un seuil, le login est refusé (429) sans même vérifier le mot de passe.
-- Auto-résolution : une fois les échecs sortis de la fenêtre, l'accès revient.
CREATE TABLE IF NOT EXISTS appweb.login_attempts (
    id          BIGSERIAL   PRIMARY KEY,
    email       TEXT        NOT NULL,           -- email tenté, en minuscules (peut ne pas exister)
    ip_address  TEXT,                           -- IP source
    success     BOOLEAN     NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE appweb.login_attempts IS
    'Audit des tentatives de connexion. Sert au verrouillage anti-brute-force '
    '(fenêtre glissante par email et par IP) et à la détection d''attaques.';

CREATE INDEX IF NOT EXISTS idx_login_attempts_email_time ON appweb.login_attempts (email, created_at);
CREATE INDEX IF NOT EXISTS idx_login_attempts_ip_time    ON appweb.login_attempts (ip_address, created_at);

-- ---------------------------------------------------------------------------
-- 1. Mapping DBF — alias de champs (priority-based)
-- ---------------------------------------------------------------------------
-- Un champ cible (target_field) peut avoir plusieurs sources possibles.
-- Quand plusieurs sources sont présentes dans un même DBF, la plus basse
-- priority gagne (NO_UAF prioritaire sur NO_UA pour le champ `uaf`).
CREATE TABLE IF NOT EXISTS appweb.dbf_field_aliases (
    id              BIGSERIAL   PRIMARY KEY,
    source_field    TEXT        NOT NULL,           -- nom DBF brut (comparé en MAJUSCULES)
    target_field    TEXT        NOT NULL,           -- nom canonique (aligné sur convention `app`)
    source_type     TEXT        NOT NULL DEFAULT 'dbf',  -- réservé pour extension (autre source que DBF)
    priority        INT         NOT NULL DEFAULT 100,    -- plus bas = prioritaire en cas de collision
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (source_field, target_field, source_type)
);

COMMENT ON TABLE appweb.dbf_field_aliases IS
    'Mapping nom DBF brut → nom canonique. priority résout les collisions '
    'lorsqu''un même target_field a plusieurs sources (ex: NO_UAF/NO_UA → uaf). '
    'Ajouter un nouveau format = INSERT, jamais une modification de code.';

INSERT INTO appweb.dbf_field_aliases (source_field, target_field, source_type, priority)
VALUES
    -- Clés / identifiants
    ('NO_UE',      'unite_d_echantillonnage_ue', 'dbf', 10),
    ('NO_PLACET',  'numero_de_parcelle',          'dbf', 10),
    ('NO_PRS',     'no_prescription',             'dbf', 10),
    ('NO_SEC_INT', 'secteur_intervention',        'dbf', 10),
    ('CHANTIER',   'chantier',                    'dbf', 10),
    -- uaf : deux sources possibles, NO_UAF prioritaire
    ('NO_UAF',     'uaf',                         'dbf', 10),
    ('NO_UA',      'uaf',                         'dbf', 20),
    ('CODE_RATF',  'code_ratf',                   'dbf', 10),
    ('NO_CONTRAT', 'contrat',                     'dbf', 10),
    ('NO_PROJET',  'projet',                      'dbf', 10),
    -- Prescription / UE
    ('Ha',         'ha_prescription',             'dbf', 10),
    ('ENTREPREN',  'entrepreneur_travaux',        'dbf', 10),
    ('DT_DEBUT',   'debut',                       'dbf', 10),
    ('DT_FIN',     'fin',                         'dbf', 10),
    ('TY_TRAIT',   'traitement',                  'dbf', 10),
    ('REGION',     'region',                      'dbf', 10),
    -- Placette / parcelle
    ('PLT_ADMIS',  'plant_ha',                    'dbf', 10),  -- plant_ha vs plant_max : à confirmer
    ('DT_PRO_SOU', 'date_production_source',      'dbf', 10),
    ('PRO_SOU',    'production_source',           'dbf', 10),
    ('TY_PLACET',  'type_placette',               'dbf', 10),
    ('MET_PROD',   'methode_production',          'dbf', 10),
    ('GARMIN',     'garmin',                      'dbf', 10)
ON CONFLICT (source_field, target_field, source_type) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 2. Lots d'import (import_batches)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS appweb.import_batches (
    id                BIGSERIAL    PRIMARY KEY,
    batch_uuid        UUID         NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    user_ref1         TEXT         NOT NULL,             -- coop (clé RLS)
    year_suffix       TEXT         NOT NULL,             -- ex: '2025-2026'
    dbf_type          TEXT         NOT NULL,             -- 'PLR', 'RXF', 'PDS'
    original_filename TEXT         NOT NULL,
    file_size_bytes   BIGINT,
    row_count         INTEGER,
    status            TEXT         NOT NULL DEFAULT 'pending',
    -- 'pending' → 'preview' (lignes stagées) → 'committed' (upsert fait) → 'error'
    error_message     TEXT,
    committed_at      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT import_batches_status_check
        CHECK (status IN ('pending', 'preview', 'committed', 'error')),
    CONSTRAINT import_batches_year_suffix_check
        CHECK (year_suffix ~ '^\d{4}-\d{4}$')
);

COMMENT ON TABLE appweb.import_batches IS
    'Un lot = un fichier DBF importé. pending → preview → committed. '
    'Les données métier (ue, parcelles) ne sont écrites qu''au commit.';

-- ---------------------------------------------------------------------------
-- 3. Lignes stagées (import_batch_rows)
-- ---------------------------------------------------------------------------
-- Chaque ligne du DBF, sous deux formes : brute (raw) et normalisée (après alias).
-- Permet de rejouer le commit sans réuploader le fichier, et de tracer l'origine.
CREATE TABLE IF NOT EXISTS appweb.import_batch_rows (
    id              BIGSERIAL   PRIMARY KEY,
    batch_id        BIGINT      NOT NULL REFERENCES appweb.import_batches(id) ON DELETE CASCADE,
    row_index       INTEGER     NOT NULL,           -- position dans le fichier (0-based)
    raw_data        JSONB       NOT NULL,           -- ligne DBF brute, clés en MAJUSCULES
    normalized_data JSONB       NOT NULL,           -- après application des alias
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (batch_id, row_index)
);

COMMENT ON TABLE appweb.import_batch_rows IS
    'Lignes stagées d''un lot d''import. normalized_data est éclaté vers '
    'appweb.ue et appweb.parcelles à l''étape commit.';

-- ---------------------------------------------------------------------------
-- 4. Unités d'échantillonnage (ue)
-- ---------------------------------------------------------------------------
-- Entité principale. Une ligne par unite_d_echantillonnage_ue distinct.
CREATE TABLE IF NOT EXISTS appweb.ue (
    id                          BIGSERIAL   PRIMARY KEY,
    ue_uuid                     UUID        NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    user_ref1                   TEXT        NOT NULL,           -- coop (clé RLS)
    year_suffix                 TEXT        NOT NULL,
    unite_d_echantillonnage_ue  TEXT        NOT NULL,           -- ex: '11161_050_ACJAS'

    -- Champs prescription (issus du DBF)
    no_prescription             TEXT,
    secteur_intervention        TEXT,
    chantier                    TEXT,
    uaf                         TEXT,                           -- NO_UAF / NO_UA unifié
    code_ratf                   TEXT,
    contrat                     TEXT,
    projet                      TEXT,
    ha_prescription             NUMERIC(12, 4),
    entrepreneur_travaux        TEXT,
    debut                       DATE,
    fin                         DATE,
    traitement                  TEXT,
    region                      TEXT,

    -- Champs à saisie manuelle (absents du DBF)
    gradient_intensite          TEXT,
    rayon                       NUMERIC(10, 2),
    stocking_av_tr              NUMERIC(12, 4),

    -- Métadonnées
    statut_validation           TEXT        NOT NULL DEFAULT 'non_valide',
    source_batch_id             BIGINT      REFERENCES appweb.import_batches(id),
    is_active                   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (user_ref1, year_suffix, unite_d_echantillonnage_ue),

    CONSTRAINT ue_statut_check
        CHECK (statut_validation IN ('non_valide', 'en_cours', 'valide')),
    CONSTRAINT ue_year_suffix_check
        CHECK (year_suffix ~ '^\d{4}-\d{4}$')
);

COMMENT ON TABLE appweb.ue IS
    'Unité d''échantillonnage — entité principale. '
    'Clé métier : (user_ref1, year_suffix, unite_d_echantillonnage_ue).';

-- ---------------------------------------------------------------------------
-- 5. Parcelles
-- ---------------------------------------------------------------------------
-- Une parcelle (placette) liée à une UE.
-- Upsert sur (ue_id, numero_de_parcelle). Disparition d'un réimport → is_active=false.
CREATE TABLE IF NOT EXISTS appweb.parcelles (
    id                      BIGSERIAL   PRIMARY KEY,
    parcelle_uuid           UUID        NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    ue_id                   BIGINT      NOT NULL REFERENCES appweb.ue(id),
    user_ref1               TEXT        NOT NULL,               -- dénormalisé pour RLS directe
    numero_de_parcelle      TEXT        NOT NULL,

    -- Champs placette (issus du DBF)
    type_placette           TEXT,
    methode_production      TEXT,
    production_source       TEXT,
    date_production_source  DATE,
    plant_ha                NUMERIC(12, 4),
    garmin                  TEXT,
    secteur_intervention    TEXT,

    -- Champs à saisie manuelle (à compléter au besoin)

    -- Métadonnées
    source_batch_id         BIGINT      REFERENCES appweb.import_batches(id),
    is_active               BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (ue_id, numero_de_parcelle)
);

COMMENT ON TABLE appweb.parcelles IS
    'Parcelles (placettes) liées à une UE. '
    'Upsert sur (ue_id, numero_de_parcelle). is_active=false si absente d''un réimport.';

-- ---------------------------------------------------------------------------
-- 6. Historique des modifications manuelles
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS appweb.edit_history (
    id              BIGSERIAL   PRIMARY KEY,
    user_ref1       TEXT        NOT NULL,
    entity_type     TEXT        NOT NULL,   -- 'ue' ou 'parcelle'
    entity_id       BIGINT      NOT NULL,
    field_name      TEXT        NOT NULL,
    old_value       TEXT,
    new_value       TEXT,
    changed_by      TEXT,
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE appweb.edit_history IS
    'Audit de chaque saisie manuelle sur ue ou parcelle.';

-- ---------------------------------------------------------------------------
-- 7. Règles de validation (configurables)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS appweb.validation_rules (
    id              BIGSERIAL   PRIMARY KEY,
    year_suffix     TEXT        NOT NULL,           -- '2026-2027' ou '*'
    module          TEXT        NOT NULL,           -- 'prescription', 'parcelle'
    traitement      TEXT        NOT NULL,           -- 'REB', 'ECL', '*'
    champ           TEXT        NOT NULL,           -- nom canonique
    rule_type       TEXT        NOT NULL,           -- 'required', 'min', 'max', 'regex', 'in_list'
    rule_value      TEXT,
    message         TEXT,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT validation_rules_module_check
        CHECK (module IN ('prescription', 'parcelle')),
    CONSTRAINT validation_rules_rule_type_check
        CHECK (rule_type IN ('required', 'min', 'max', 'regex', 'in_list'))
);

COMMENT ON TABLE appweb.validation_rules IS
    'Règles de validation par année / module / traitement. '
    'Remplace les colonnes orange du DATA_MANUELLE. ''*'' = transversal.';

INSERT INTO appweb.validation_rules (year_suffix, module, traitement, champ, rule_type, message)
VALUES
    ('*',         'prescription', '*',   'no_prescription',  'required', 'Le numéro de prescription est obligatoire'),
    ('*',         'prescription', '*',   'uaf',              'required', 'L''UAF est obligatoire'),
    ('*',         'prescription', '*',   'traitement',       'required', 'Le traitement est obligatoire'),
    ('*',         'prescription', '*',   'ha_prescription',  'required', 'La superficie prescrite est obligatoire'),
    ('2026-2027', 'prescription', 'REB', 'plant_ha',         'required', 'plant_ha est obligatoire pour REB 2026-2027'),
    ('*',         'parcelle',     '*',   'numero_de_parcelle','required', 'Le numéro de parcelle est obligatoire')
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- 8. Résultats de validation
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS appweb.validation_results (
    id              BIGSERIAL   PRIMARY KEY,
    user_ref1       TEXT        NOT NULL,
    run_uuid        UUID        NOT NULL,
    entity_type     TEXT        NOT NULL,                   -- 'ue' ou 'parcelle'
    entity_id       BIGINT      NOT NULL,
    rule_id         BIGINT      NOT NULL REFERENCES appweb.validation_rules(id),
    is_valid        BOOLEAN     NOT NULL,
    message         TEXT,
    validated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE appweb.validation_results IS
    'Résultats de chaque passe de validation, regroupés par run_uuid.';

-- ---------------------------------------------------------------------------
-- 9. Log de génération Kizeo
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS appweb.kizeo_generation_log (
    id              BIGSERIAL   PRIMARY KEY,
    user_ref1       TEXT        NOT NULL,
    ue_id           BIGINT      NOT NULL REFERENCES appweb.ue(id),
    year_suffix     TEXT        NOT NULL,
    status          TEXT        NOT NULL DEFAULT 'simule',  -- 'simule' → 'envoye' → 'erreur'
    payload_json    JSONB,
    response_json   JSONB,
    error_message   TEXT,
    generated_by    TEXT,
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT kizeo_gen_status_check
        CHECK (status IN ('simule', 'envoye', 'erreur'))
);

COMMENT ON TABLE appweb.kizeo_generation_log IS
    'Trace chaque génération de liste Kizeo. status=''simule'' tant que l''API n''est pas branchée.';

-- ---------------------------------------------------------------------------
-- 10. Index
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_aliases_active        ON appweb.dbf_field_aliases (target_field) WHERE is_active;
CREATE INDEX IF NOT EXISTS idx_ue_user_ref1_year     ON appweb.ue (user_ref1, year_suffix);
CREATE INDEX IF NOT EXISTS idx_ue_statut             ON appweb.ue (statut_validation) WHERE is_active;
CREATE INDEX IF NOT EXISTS idx_parcelles_ue_id       ON appweb.parcelles (ue_id);
CREATE INDEX IF NOT EXISTS idx_parcelles_user_ref1   ON appweb.parcelles (user_ref1);
CREATE INDEX IF NOT EXISTS idx_batches_user_year     ON appweb.import_batches (user_ref1, year_suffix);
CREATE INDEX IF NOT EXISTS idx_batch_rows_batch      ON appweb.import_batch_rows (batch_id);
CREATE INDEX IF NOT EXISTS idx_val_results_run       ON appweb.validation_results (run_uuid);
CREATE INDEX IF NOT EXISTS idx_val_results_entity    ON appweb.validation_results (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_edit_history_entity   ON appweb.edit_history (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_kizeo_gen_ue          ON appweb.kizeo_generation_log (ue_id);

-- ---------------------------------------------------------------------------
-- 11. RLS (préparée, commentée — à activer après le modèle d'auth portail)
-- ---------------------------------------------------------------------------
-- ALTER TABLE appweb.ue ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY ue_rls ON appweb.ue USING (user_ref1 = app.current_coop());
-- ALTER TABLE appweb.parcelles ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY parcelles_rls ON appweb.parcelles USING (user_ref1 = app.current_coop());
-- (idem import_batches, import_batch_rows, validation_results, edit_history, kizeo_generation_log)

COMMIT;
