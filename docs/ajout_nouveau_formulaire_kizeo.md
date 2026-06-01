# Ajout d'un nouveau formulaire Kizeo
*Procédure complète — de la création du formulaire dans Kizeo à l'ingestion opérationnelle*

---

# 0. Prérequis

Avant de commencer :
- Le formulaire existe dans Kizeo et contient au moins un enregistrement de test
- Les coops concernées sont déjà dans `app.coops` (sinon → [ajout_nouvelle_coop.md](ajout_nouvelle_coop.md))
- Les exports Excel/PDF sont configurés dans Kizeo si nécessaire

---

# 1. Appeler `kizeo_schema_builder.py`

C'est l'unique étape de bootstrap. Un seul appel fait tout :

1. Synchronise le catalogue Kizeo pour ce formulaire (`app.kizeo_forms`, `app.kizeo_form_exports`, `app.kizeo_form_fields`, `app.kizeo_form_lists`)
2. Génère et applique le DDL PostgreSQL (schéma `<form_id>`, tables parent + sous-formulaires) — idempotent, safe à relancer
3. Active la RLS sur toutes les tables via `app.ensure_rls_for_table()` — automatique
4. Importe le premier enregistrement Kizeo (appelle `fetch_data_kizeo_api` en interne)

Dans Kizeo Forms, ouvrir le formulaire **"Lancer script python"** (form_id `1108810`) et remplir :

| Champ | Valeur |
|---|---|
| Opération a effectuer | *(opération correspondante)* |
| Script a lancer | `kizeo_schema_builder.py` |
| BD a mettre à jour ? | `<nom_base>` |
| ID formulaire a mettre à jour ? | `880205` |
| ID liste a mettre à jour ? | *(laisser vide)* |

Soumettre → déclenche Make → Flask → `kizeo_schema_builder.py`.

**Via curl (debug local uniquement) :**

```bash
curl -X POST http://localhost:5000/run \
  -H "X-Script-Name: kizeo_schema_builder.py" \
  -H "X-Auth-Key: <clé>" \
  -H "Content-Type: application/json" \
  -d '{"form_id": "880205", "bd": "<nom_base>", "data_id": "<data_id>"}'
```

**Résultat attendu :**

```json
{
  "status": "success",
  "form_id": "880205",
  "schema": "880205",
  "tables": ["880205", "880205_sous1", ...],
  "catalog_status": "ok",
  "fetch_status": "success"
}
```

---

# 2. Vérifier le résultat en base

```sql
-- Schéma et tables créés
SELECT table_name
FROM information_schema.tables
WHERE table_schema = '880205'
ORDER BY table_name;

-- RLS activée
SELECT relname, relrowsecurity
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = '880205';

-- Catalog synchronized
SELECT * FROM app.kizeo_forms WHERE form_id = '880205';
SELECT * FROM app.kizeo_form_exports WHERE form_id = '880205';

-- Premier enregistrement importé
SELECT * FROM "880205"."880205" LIMIT 5;
```

---

# 3. Configurer les webhooks Kizeo → Make

Chaque scénario Make a une URL de webhook. Il faut déclarer ces URLs dans la configuration du formulaire dans Kizeo (onglet **Webhooks / Notifications**).

**Règle : 2 webhooks par script — un pour les événements normaux, un pour les suppressions.**

Pour un formulaire avec ingestion BD + export SharePoint, c'est **4 webhooks** à configurer dans Kizeo :

| # | Événement Kizeo | Scénario Make → Flask | Payload Make → Flask |
|---|---|---|---|
| 1 | Nouvelle donnée / Modification | `fetch_data_kizeo_api.py` | `{"form_id": "880205", "data_id": "...", "bd": "..."}` |
| 2 | Suppression | `fetch_data_kizeo_api.py` | `{"form_id": "880205", "data_id": "...", "bd": "...", "deleted": true}` |
| 3 | Nouvelle donnée / Modification | `name_builder.py` | `{"form_id": "880205", "data_id": "...", "user_id": "...", "bd": "...", "export_name": "...", "year_suffix": "...", "ue": "...", "region": "..."}` |
| 4 | Suppression | `name_builder.py` | *(même payload + champ delete selon config Make)* |

**Dans Kizeo** : Paramètres du formulaire → Webhooks → Ajouter l'URL Make pour chaque événement.

**Dans Make** : chaque scénario reçoit le webhook Kizeo, mappe les champs, puis appelle Flask `/run` avec le bon `X-Script-Name`.

> Si le formulaire n'a pas d'export SharePoint, seuls les webhooks 1 et 2 sont nécessaires.

Référence payloads Make → Flask : [payloads_by_script.md](payloads_by_script.md)

---

# 4. Configurer les exports Excel/PDF (si nécessaire)

Si le formulaire a des exports à envoyer sur SharePoint :

## 4.1. Vérifier les exports dans le catalogue

```sql
SELECT form_id, export_id, name_excel, name_pdf
FROM app.kizeo_form_exports
WHERE form_id = '880205';
```

Si vide → les exports ne sont pas encore configurés dans Kizeo, ou le catalogue n'est pas synchronisé.

Resynchroniser :

```
POST /run
X-Script-Name: sync_kizeo_catalog.py
```

## 4.2. Vérifier que `name_builder.py` résout correctement

`name_builder.py` lit `app.kizeo_form_exports` pour résoudre `export_id` depuis `export_name`. S'assurer que les colonnes `name_excel` et `name_pdf` sont bien renseignées dans le catalogue.

## 4.3. Créer le scénario Make pour les exports

```
POST /run
X-Script-Name: name_builder.py
X-Auth-Key: <clé courante>

{
  "form_id": "880205",
  "data_id": "{{data_id}}",
  "export_name": "{{nom_export}}",
  "year_suffix": "{{annee}}",
  "ue": "{{ue}}",
  "bd": "<nom_base>"
}
```

---

# 5. Provisionner les accès ODBC

Après que les premières données sont présentes dans le schéma (avec `user_ref1` renseigné) :

```sql
SELECT * FROM app.refresh_coop_schema_access();
SELECT * FROM app.apply_coop_schema_grants();
```

Cela donne automatiquement accès en lecture aux rôles ODBC des coops qui ont des données dans ce formulaire.

---

# 6. Checklist finale

- [ ] Formulaire existant dans Kizeo avec au moins un enregistrement
- [ ] `kizeo_schema_builder.py` appelé avec succès → schéma + tables créés + RLS active
- [ ] Données visibles dans `"880205"."880205"`
- [ ] Catalogue synchronisé (`app.kizeo_forms`, `app.kizeo_form_exports`)
- [ ] Scénario Make régulier configuré (`fetch_data_kizeo_api.py`)
- [ ] Si exports : `app.kizeo_form_exports` contient `name_excel`/`name_pdf`, scénario Make exports créé
- [ ] `refresh_coop_schema_access()` + `apply_coop_schema_grants()` lancés
- [ ] Test end-to-end depuis Make (ingestion + export si applicable)

---

# 7. Notes

**Le DDL est idempotent** : relancer `kizeo_schema_builder.py` sur un formulaire déjà créé ne casse rien — il ajoute les colonnes manquantes et réapplique la RLS.

**RLS appliquée automatiquement** : pas besoin de la configurer manuellement, `apply_ddl` appelle `app.ensure_rls_for_table()` sur chaque table du schéma.

**`kizeo_schema_builder.py` n'est pas dans la boucle régulière** : il sert uniquement au bootstrap initial (ou en cas d'ajout de champs dans le formulaire Kizeo). Les ingestions quotidiennes passent par `fetch_data_kizeo_api.py`.

---

# 8. Voir aussi

- [pipeline_kizeo.md](pipeline_kizeo.md) — flux d'ingestion régulier
- [pipeline_exports.md](pipeline_exports.md) — flux exports Excel/PDF
- [payloads_by_script.md](payloads_by_script.md) — référence des payloads
- [postgresql_schema.md](postgresql_schema.md) — structure de la base
- [bd_acces_autorisation.md](bd_acces_autorisation.md) — DISCOVER → REFRESH → APPLY
- [ajout_nouvelle_coop.md](ajout_nouvelle_coop.md) — onboarding d'une coop
