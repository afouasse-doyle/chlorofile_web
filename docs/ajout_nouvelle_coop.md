# Ajout d'une nouvelle coop
*Procédure complète — de zéro à une coop opérationnelle*

---

# 0. Identifiants à décider avant de commencer

| Identifiant | Description | Exemple |
|---|---|---|
| `coop_code` | Clé primaire dans `app.coops` — unique, majuscules | `ABIFOR` |
| `user_ref1` | Clé RLS — en général = `coop_code` | `ABIFOR` |
| `directory` | Nom du dossier SharePoint — peut différer de `coop_code` | `CFGaspesie`, `1-Gestion` |
| `login_name` | Utilisateur ODBC PostgreSQL | `abifor_odbc` |
| `role_name` | Rôle read-only PostgreSQL | `coop_ro_abifor` |

> `directory` n'est pas toujours identique à `coop_code`. Exemples : CFG → `CFGaspesie`, CFHPV → `CFHautPlanVert`, FQCF → `1-Gestion`. C'est la valeur qui construit le chemin SharePoint.

---

# 1. PostgreSQL — Créer le rôle et l'utilisateur ODBC

## 1.1. Créer le rôle read-only

```sql
CREATE ROLE coop_ro_abifor NOLOGIN;
```

## 1.2. Positionner la variable de session RLS sur le rôle

Le rôle doit automatiquement setter `app.user_ref1` à la connexion pour que `app.current_coop()` retourne le bon code coop et que la RLS s'applique correctement :

```sql
ALTER ROLE coop_ro_abifor SET app.user_ref1 = 'ABIFOR';
```

## 1.3. Créer l'utilisateur ODBC

```sql
CREATE USER abifor_odbc WITH PASSWORD '...' CONNECTION LIMIT 10;
GRANT coop_ro_abifor TO abifor_odbc;
```

Stocker le mot de passe dans 1Password (`INFRA - PROD`).

## 1.4. Accès au schéma `app`

Les tables `app.*` accessibles en lecture (prescriptions, parcelles, secteur_intervention_reb, etc.) :

```sql
GRANT USAGE ON SCHEMA app TO coop_ro_abifor;
GRANT SELECT ON ALL TABLES IN SCHEMA app TO coop_ro_abifor;
ALTER DEFAULT PRIVILEGES FOR ROLE chlorofile2_app IN SCHEMA app
    GRANT SELECT ON TABLES TO coop_ro_abifor;
```

---

# 2. Insérer dans `app.coops`

Source de vérité pour le chemin SharePoint et la RLS. À faire avant tout le reste.

```sql
INSERT INTO app.coops (coop_code, coop_name, directory, user_ref1, login_name)
VALUES ('ABIFOR', 'Nom complet de la coop', 'ABIFOR', 'ABIFOR', 'abifor_odbc');
```

Vérifier :

```sql
SELECT * FROM app.coops WHERE coop_code = 'ABIFOR';
```

---

# 3. Kizeo — Vérifier les utilisateurs

Les utilisateurs Kizeo de cette coop doivent avoir le bon `user_ref1` dans `app.kizeo_users`. Cette table est alimentée par `create_kizeo_user_structure.py`.

Vérifier après le premier passage du script :

```sql
SELECT * FROM app.kizeo_users WHERE user_ref1 = 'ABIFOR';
```

Si vide → relancer `create_kizeo_user_structure.py`. S'assurer que les utilisateurs Kizeo de la coop ont bien `user_ref1 = 'ABIFOR'` assigné dans Kizeo.

---

# 4. SharePoint — Dossier racine

Créer manuellement le dossier racine de la coop dans SharePoint (ou le laisser aux scripts qui le créent automatiquement au premier upload) :

```
General/
 └── ABIFOR/          ← valeur de app.coops.directory
     └── 2025-2026/   ← créé automatiquement par les scripts lors du premier export
```

Voir [sharepoint_structure.md](sharepoint_structure.md) pour la structure complète.

---

# 5. Accès aux schémas formulaires — REFRESH + APPLY

Une fois que des données arrivent dans les schémas formulaires (ex: `880205`) avec `user_ref1 = 'ABIFOR'`, provisionner les accès ODBC :

```sql
-- Découvrir les accès admissibles et les enregistrer dans app.coop_schema_access
SELECT * FROM app.refresh_coop_schema_access();

-- Appliquer les GRANT manquants
SELECT * FROM app.apply_coop_schema_grants();
```

À relancer chaque fois qu'un nouveau formulaire est déployé pour cette coop.

Voir [bd_acces_autorisation.md](bd_acces_autorisation.md) pour le détail du système DISCOVER → REFRESH → APPLY.

---

# 6. `pg_hba.conf` — Autoriser la connexion

Si l'IP du client n'est pas déjà couverte par une règle existante, ajouter dans `pg_hba.conf` :

```conf
hostssl  <db>   abifor_odbc   <ip_client>/32   scram-sha-256
```

Recharger PostgreSQL après modification :

```bash
pg_ctl reload
```

---

# 7. Make — Vérifier les scénarios

Les scénarios Make existants sont génériques (ils opèrent sur `form_id` + `user_ref1` qui vient des données). En général aucune modification n'est nécessaire.

Si la coop a des formulaires ou exports spécifiques non couverts par les scénarios existants → créer un nouveau scénario Make pointant vers le bon `X-Script-Name`.

---

# 8. ODBC — Configurer la connexion côté client

Sur le poste client (Excel, Power BI, QGIS) :

1. Installer le driver ODBC PostgreSQL
2. Créer un DSN système :
   - **Host** : adresse du serveur PG
   - **Port** : `5432`
   - **Database** : nom de la base
   - **User** : `abifor_odbc`
   - **Password** : (depuis 1Password)
   - **SSL Mode** : `require`
3. Tester la connexion
4. Vérifier que la RLS filtre correctement (la coop ne voit que ses données)

---

# 9. Checklist finale

- [ ] `coop_code`, `user_ref1`, `directory`, `login_name` décidés et cohérents
- [ ] Rôle `coop_ro_<coop>` créé avec `SET app.user_ref1 = '...'`
- [ ] Utilisateur ODBC créé, mot de passe stocké dans 1Password
- [ ] GRANTs sur schéma `app` appliqués
- [ ] Ligne insérée dans `app.coops`
- [ ] `app.kizeo_users` peuplé pour cette coop (via `create_kizeo_user_structure.py`)
- [ ] Dossier SharePoint racine créé
- [ ] Premières données reçues via pipeline Kizeo
- [ ] `refresh_coop_schema_access()` + `apply_coop_schema_grants()` lancés
- [ ] `pg_hba.conf` mis à jour si nécessaire et rechargé
- [ ] Connexion ODBC testée côté client — vérifier la RLS

---

# 10. Voir aussi

- [postgresql_schema.md](postgresql_schema.md) — structure de la base, RLS, rôles
- [bd_acces_autorisation.md](bd_acces_autorisation.md) — système DISCOVER → REFRESH → APPLY
- [sharepoint_structure.md](sharepoint_structure.md) — structure des dossiers SharePoint
- [security_env.md](security_env.md) — principes de sécurité et gestion des mots de passe
- [pipeline_kizeo.md](pipeline_kizeo.md) — ingestion des données formulaires
