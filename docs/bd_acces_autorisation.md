# Gestion des accès BD — ODBC par coop
*Aide-mémoire : provisionnement automatique des GRANT PostgreSQL pour les rôles ODBC*

Le système fonctionne en 3 étapes : **DISCOVER → REFRESH → APPLY**

- **DISCOVER** : détecte quels schémas/coops sont éligibles (table + RLS + user_ref1 présents)
- **REFRESH** : écrit les accès admissibles dans `app.coop_schema_access` (sans faire de GRANT)
- **APPLY** : exécute réellement les GRANT, seulement ce qui manque

---

# 1. Tables de contrôle

À créer une seule fois.

```sql
CREATE TABLE IF NOT EXISTS app.coop_schema_access (
    user_ref1 text NOT NULL,
    coop_role text NOT NULL,
    schema_name text NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    discovered_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    applied_at timestamptz,
    last_status text,
    last_reason text,

    PRIMARY KEY (user_ref1, schema_name),

    CONSTRAINT chk_coop_schema_access_schema_safe
        CHECK (schema_name ~ '^[0-9]+$'),

    CONSTRAINT chk_coop_schema_access_no_app
        CHECK (schema_name <> 'app')
);

CREATE TABLE IF NOT EXISTS app.coop_schema_access_audit (
    id bigserial PRIMARY KEY,
    event_at timestamptz NOT NULL DEFAULT now(),
    action text NOT NULL,
    user_ref1 text,
    coop_role text,
    schema_name text,
    status text NOT NULL,
    reason text
);
```

---

# 2. Fonction DISCOVER

Lit l'état réel de la base et détermine ce qui est éligible. Ne modifie rien.

```sql
CREATE OR REPLACE FUNCTION app.discover_coop_schema_access()
RETURNS TABLE (
    schema_name text,
    user_ref1 text,
    coop_role text,
    eligible boolean,
    reason text,
    table_exists boolean,
    user_ref1_column_exists boolean,
    rls_enabled boolean,
    role_exists boolean
)
LANGUAGE plpgsql
AS $$
DECLARE
    s record;
    u record;
    v_table_oid oid;
    v_rls_enabled boolean;
    v_user_ref1_exists boolean;
    v_role_exists boolean;
BEGIN
    FOR s IN
        SELECT nspname AS schema_name
        FROM pg_namespace
        WHERE nspname ~ '^[0-9]+$'
        ORDER BY nspname
    LOOP
        v_table_oid := NULL;
        v_rls_enabled := false;
        v_user_ref1_exists := false;

        SELECT c.oid, c.relrowsecurity
        INTO v_table_oid, v_rls_enabled
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = s.schema_name
          AND c.relname = s.schema_name
          AND c.relkind IN ('r', 'p')
        LIMIT 1;

        IF v_table_oid IS NULL THEN
            schema_name := s.schema_name;
            user_ref1 := NULL;
            coop_role := NULL;
            eligible := false;
            reason := 'SKIP: table principale absente';
            table_exists := false;
            user_ref1_column_exists := false;
            rls_enabled := false;
            role_exists := false;
            RETURN NEXT;
            CONTINUE;
        END IF;

        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns c
            WHERE c.table_schema = s.schema_name
              AND c.table_name = s.schema_name
              AND c.column_name = 'user_ref1'
        )
        INTO v_user_ref1_exists;

        IF NOT v_user_ref1_exists THEN
            schema_name := s.schema_name;
            user_ref1 := NULL;
            coop_role := NULL;
            eligible := false;
            reason := 'SKIP: colonne user_ref1 absente';
            table_exists := true;
            user_ref1_column_exists := false;
            rls_enabled := v_rls_enabled;
            role_exists := false;
            RETURN NEXT;
            CONTINUE;
        END IF;

        IF NOT v_rls_enabled THEN
            schema_name := s.schema_name;
            user_ref1 := NULL;
            coop_role := NULL;
            eligible := false;
            reason := 'SKIP: RLS non activée';
            table_exists := true;
            user_ref1_column_exists := true;
            rls_enabled := false;
            role_exists := false;
            RETURN NEXT;
            CONTINUE;
        END IF;

        FOR u IN EXECUTE format(
            'SELECT DISTINCT NULLIF(btrim(user_ref1::text), '''') AS user_ref1
             FROM %I.%I
             WHERE NULLIF(btrim(user_ref1::text), '''') IS NOT NULL
             ORDER BY 1',
            s.schema_name,
            s.schema_name
        )
        LOOP
            SELECT EXISTS (
                SELECT 1
                FROM pg_roles r
                WHERE r.rolname = c.login_name
            )
            INTO v_role_exists
            FROM app.coops c
            WHERE c.user_ref1 = u.user_ref1;

            schema_name := s.schema_name;
            user_ref1 := u.user_ref1;

            SELECT c.login_name
            INTO coop_role
            FROM app.coops c
            WHERE c.user_ref1 = u.user_ref1;

            table_exists := true;
            user_ref1_column_exists := true;
            rls_enabled := true;
            role_exists := COALESCE(v_role_exists, false);

            IF coop_role IS NULL THEN
                eligible := false;
                reason := 'SKIP: user_ref1 absent de app.coops';
            ELSIF NOT role_exists THEN
                eligible := false;
                reason := 'SKIP: rôle PostgreSQL inexistant';
            ELSE
                eligible := true;
                reason := 'OK: accès admissible';
            END IF;

            RETURN NEXT;
        END LOOP;
    END LOOP;
END;
$$;
```

## Requêtes utiles

```sql
-- Voir qui devrait avoir accès
SELECT *
FROM app.discover_coop_schema_access()
ORDER BY schema_name, user_ref1;

-- Voir ce qui est bloqué et pourquoi
SELECT *
FROM app.discover_coop_schema_access()
WHERE eligible = false
ORDER BY schema_name, reason;

-- Voir ce qui serait autorisé
SELECT *
FROM app.discover_coop_schema_access()
WHERE eligible = true
ORDER BY schema_name, user_ref1;
```

---

# 3. Fonction REFRESH

Écrit les accès admissibles dans `app.coop_schema_access`. Aucun GRANT ici — elle écrit seulement les accès admissibles détectés.

```sql
CREATE OR REPLACE FUNCTION app.refresh_coop_schema_access()
RETURNS TABLE (
    out_user_ref1 text,
    out_coop_role text,
    out_schema_name text,
    out_status text,
    out_reason text
)
LANGUAGE plpgsql
AS $$
DECLARE
    r record;
BEGIN
    FOR r IN
        SELECT d.*
        FROM app.discover_coop_schema_access() AS d
    LOOP
        IF r.eligible = true THEN

            INSERT INTO app.coop_schema_access (
                user_ref1,
                coop_role,
                schema_name,
                enabled,
                discovered_at,
                last_seen_at,
                last_status,
                last_reason
            )
            VALUES (
                r.user_ref1,
                r.coop_role,
                r.schema_name,
                true,
                now(),
                now(),
                'DISCOVERED',
                r.reason
            )
            ON CONFLICT (user_ref1, schema_name)
            DO UPDATE SET
                coop_role = EXCLUDED.coop_role,
                enabled = true,
                last_seen_at = now(),
                last_status = 'DISCOVERED',
                last_reason = EXCLUDED.last_reason;

            INSERT INTO app.coop_schema_access_audit (
                action,
                user_ref1,
                coop_role,
                schema_name,
                status,
                reason
            )
            VALUES (
                'REFRESH',
                r.user_ref1,
                r.coop_role,
                r.schema_name,
                'OK',
                r.reason
            );

            out_user_ref1 := r.user_ref1;
            out_coop_role := r.coop_role;
            out_schema_name := r.schema_name;
            out_status := 'OK';
            out_reason := r.reason;
            RETURN NEXT;

        ELSE
            INSERT INTO app.coop_schema_access_audit (
                action,
                user_ref1,
                coop_role,
                schema_name,
                status,
                reason
            )
            VALUES (
                'REFRESH_SKIP',
                r.user_ref1,
                r.coop_role,
                r.schema_name,
                'SKIP',
                r.reason
            );
        END IF;
    END LOOP;
END;
$$;
```

## Tester le refresh

```sql
SELECT *
FROM app.refresh_coop_schema_access()
ORDER BY schema_name, user_ref1;

-- Vérifier ce qui a été enregistré
SELECT *
FROM app.coop_schema_access
ORDER BY schema_name, user_ref1;

-- Vérifier l'audit
SELECT *
FROM app.coop_schema_access_audit
ORDER BY id DESC
LIMIT 100;
```

---

# 4. Fonction APPLY

Applique réellement les GRANT. Lit `app.coop_schema_access` (où `enabled = true`) et applique seulement ce qui manque.

**SUPER IMPORTANT** : le système repose sur RLS active et correcte. Sans RLS, un GRANT SELECT = accès complet à toutes les données. DISCOVER bloque déjà (`pas de RLS → SKIP`, `pas de user_ref1 → SKIP`), donc on est safe — mais c'est le dernier garde-fou.

```sql
CREATE OR REPLACE FUNCTION app.apply_coop_schema_grants()
RETURNS TABLE (
    out_user_ref1 text,
    out_coop_role text,
    out_schema_name text,
    out_status text,
    out_reason text
)
LANGUAGE plpgsql
AS $$
DECLARE
    r record;

    v_table_oid oid;
    v_rls_enabled boolean;
    v_user_ref1_column_exists boolean;
    v_role_exists boolean;

    v_schema_usage_ok boolean;
    v_tables_select_ok boolean;
    v_sequences_usage_ok boolean;

    v_did_apply boolean;
BEGIN
    FOR r IN
        SELECT *
        FROM app.coop_schema_access
        WHERE enabled = true
          AND schema_name ~ '^[0-9]+$'
          AND schema_name <> 'app'
        ORDER BY schema_name, user_ref1
    LOOP
        BEGIN
            v_did_apply := false;

            -- 1) Role PostgreSQL existe
            SELECT EXISTS (
                SELECT 1
                FROM pg_roles
                WHERE rolname = r.coop_role
            )
            INTO v_role_exists;

            IF NOT v_role_exists THEN
                INSERT INTO app.coop_schema_access_audit (
                    action, user_ref1, coop_role, schema_name, status, reason
                )
                VALUES (
                    'APPLY_SKIP', r.user_ref1, r.coop_role, r.schema_name, 'SKIP',
                    'Rôle PostgreSQL inexistant'
                );

                out_user_ref1 := r.user_ref1;
                out_coop_role := r.coop_role;
                out_schema_name := r.schema_name;
                out_status := 'SKIP';
                out_reason := 'Rôle PostgreSQL inexistant';
                RETURN NEXT;
                CONTINUE;
            END IF;

            -- 2) Table principale + RLS
            SELECT c.oid, c.relrowsecurity
            INTO v_table_oid, v_rls_enabled
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = r.schema_name
              AND c.relname = r.schema_name
              AND c.relkind IN ('r', 'p')
            LIMIT 1;

            IF v_table_oid IS NULL THEN
                INSERT INTO app.coop_schema_access_audit (
                    action, user_ref1, coop_role, schema_name, status, reason
                )
                VALUES (
                    'APPLY_SKIP', r.user_ref1, r.coop_role, r.schema_name, 'SKIP',
                    'Table principale absente au moment du APPLY'
                );

                out_user_ref1 := r.user_ref1;
                out_coop_role := r.coop_role;
                out_schema_name := r.schema_name;
                out_status := 'SKIP';
                out_reason := 'Table principale absente au moment du APPLY';
                RETURN NEXT;
                CONTINUE;
            END IF;

            IF NOT COALESCE(v_rls_enabled, false) THEN
                INSERT INTO app.coop_schema_access_audit (
                    action, user_ref1, coop_role, schema_name, status, reason
                )
                VALUES (
                    'APPLY_SKIP', r.user_ref1, r.coop_role, r.schema_name, 'SKIP',
                    'RLS non activée au moment du APPLY'
                );

                out_user_ref1 := r.user_ref1;
                out_coop_role := r.coop_role;
                out_schema_name := r.schema_name;
                out_status := 'SKIP';
                out_reason := 'RLS non activée au moment du APPLY';
                RETURN NEXT;
                CONTINUE;
            END IF;

            -- 3) Colonne user_ref1 existe encore
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns c
                WHERE c.table_schema = r.schema_name
                  AND c.table_name = r.schema_name
                  AND c.column_name = 'user_ref1'
            )
            INTO v_user_ref1_column_exists;

            IF NOT v_user_ref1_column_exists THEN
                INSERT INTO app.coop_schema_access_audit (
                    action, user_ref1, coop_role, schema_name, status, reason
                )
                VALUES (
                    'APPLY_SKIP', r.user_ref1, r.coop_role, r.schema_name, 'SKIP',
                    'Colonne user_ref1 absente au moment du APPLY'
                );

                out_user_ref1 := r.user_ref1;
                out_coop_role := r.coop_role;
                out_schema_name := r.schema_name;
                out_status := 'SKIP';
                out_reason := 'Colonne user_ref1 absente au moment du APPLY';
                RETURN NEXT;
                CONTINUE;
            END IF;

            -- 4) Vérifier les GRANT déjà existants
            SELECT has_schema_privilege(r.coop_role, r.schema_name, 'USAGE')
            INTO v_schema_usage_ok;

            SELECT NOT EXISTS (
                SELECT 1
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = r.schema_name
                  AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
                  AND NOT has_table_privilege(r.coop_role, c.oid, 'SELECT')
            )
            INTO v_tables_select_ok;

            SELECT NOT EXISTS (
                SELECT 1
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = r.schema_name
                  AND c.relkind = 'S'
                  AND NOT has_sequence_privilege(r.coop_role, c.oid, 'USAGE')
            )
            INTO v_sequences_usage_ok;

            -- 5) Appliquer seulement ce qui manque
            IF NOT v_schema_usage_ok THEN
                EXECUTE format(
                    'GRANT USAGE ON SCHEMA %I TO %I',
                    r.schema_name,
                    r.coop_role
                );
                v_did_apply := true;
            END IF;

            IF NOT v_tables_select_ok THEN
                EXECUTE format(
                    'GRANT SELECT ON ALL TABLES IN SCHEMA %I TO %I',
                    r.schema_name,
                    r.coop_role
                );
                v_did_apply := true;
            END IF;

            IF NOT v_sequences_usage_ok THEN
                EXECUTE format(
                    'GRANT USAGE ON ALL SEQUENCES IN SCHEMA %I TO %I',
                    r.schema_name,
                    r.coop_role
                );
                v_did_apply := true;
            END IF;

            -- 6) Default privileges : idempotent, safe à relancer
            EXECUTE format(
                'ALTER DEFAULT PRIVILEGES FOR ROLE chlorofile2_app IN SCHEMA %I GRANT SELECT ON TABLES TO %I',
                r.schema_name,
                r.coop_role
            );

            EXECUTE format(
                'ALTER DEFAULT PRIVILEGES FOR ROLE chlorofile2_app IN SCHEMA %I GRANT USAGE ON SEQUENCES TO %I',
                r.schema_name,
                r.coop_role
            );

            -- On considère que default privileges ont été revalidés/appliqués
            v_did_apply := true;

            IF v_did_apply THEN
                INSERT INTO app.coop_schema_access_audit (
                    action, user_ref1, coop_role, schema_name, status, reason
                )
                VALUES (
                    'APPLY_OK', r.user_ref1, r.coop_role, r.schema_name, 'OK',
                    'GRANT vérifiés/appliqués'
                );

                UPDATE app.coop_schema_access
                SET applied_at = now(),
                    last_status = 'APPLIED',
                    last_reason = 'GRANT vérifiés/appliqués'
                WHERE user_ref1 = r.user_ref1
                  AND schema_name = r.schema_name;

                out_status := 'OK';
                out_reason := 'GRANT vérifiés/appliqués';
            ELSE
                INSERT INTO app.coop_schema_access_audit (
                    action, user_ref1, coop_role, schema_name, status, reason
                )
                VALUES (
                    'APPLY_NOOP', r.user_ref1, r.coop_role, r.schema_name, 'OK',
                    'Droits déjà présents'
                );

                out_status := 'OK';
                out_reason := 'Droits déjà présents';
            END IF;

            out_user_ref1 := r.user_ref1;
            out_coop_role := r.coop_role;
            out_schema_name := r.schema_name;
            RETURN NEXT;

        EXCEPTION WHEN OTHERS THEN
            INSERT INTO app.coop_schema_access_audit (
                action, user_ref1, coop_role, schema_name, status, reason
            )
            VALUES (
                'APPLY_ERROR', r.user_ref1, r.coop_role, r.schema_name, 'ERROR',
                SQLERRM
            );

            UPDATE app.coop_schema_access
            SET last_status = 'ERROR',
                last_reason = SQLERRM
            WHERE user_ref1 = r.user_ref1
              AND schema_name = r.schema_name;

            out_user_ref1 := r.user_ref1;
            out_coop_role := r.coop_role;
            out_schema_name := r.schema_name;
            out_status := 'ERROR';
            out_reason := SQLERRM;
            RETURN NEXT;
        END;
    END LOOP;
END;
$$;
```

## Tester le APPLY

```sql
SELECT *
FROM app.apply_coop_schema_grants()
ORDER BY out_schema_name, out_user_ref1;
```

---

# 5. Workflow complet

Quand tu ajoutes un nouveau formulaire (nouveau schéma `form_id` avec données) :

1. Les données arrivent via `fetch_data_kizeo_api` → `upsert_data_postgresql`
2. `user_ref1` est présent dans les lignes
3. Lancer le REFRESH :
   ```sql
   SELECT * FROM app.refresh_coop_schema_access();
   ```
4. Lancer le APPLY :
   ```sql
   SELECT * FROM app.apply_coop_schema_grants();
   ```

Tout se fait automatiquement — les coops qui ont des données dans le schéma et dont le rôle PostgreSQL existe reçoivent les droits, les autres sont skippées avec la raison dans l'audit.

---

# 6. Voir aussi

- [postgresql_schema.md](postgresql_schema.md) — structure complète de la base (RLS, rôles, schémas)
- [security_env.md](security_env.md) — principes de sécurité et rôles PostgreSQL
