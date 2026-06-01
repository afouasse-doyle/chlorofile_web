# Ajout d'un utilisateur Kizeo
*Procédure à suivre après chaque création ou modification d'utilisateur dans Kizeo*

---

# Pourquoi c'est critique

`app.kizeo_users` est la source de vérité qui fait le lien entre un `_user_id` Kizeo et un `user_ref1` (code coop). Ce lien est utilisé par **tous** les scripts qui traitent des données :

- `upsert_data_postgresql.py` — résout `user_ref1` pour la RLS et l'écriture en BD
- `name_builder.py` — résout `user_ref1` pour construire le chemin SharePoint
- `ddif_name_builder.py` — idem

**Si un utilisateur n'est pas dans `app.kizeo_users` :**
- `user_ref1` ne peut pas être résolu → `NULL`
- La donnée est rejetée ou écrite sans `user_ref1`
- La RLS bloque l'accès, les exports vont au mauvais endroit, les logs sont incorrects

---

# Procédure

## Étape 1 — Créer l'utilisateur dans Kizeo

Dans l'interface Kizeo admin :
- Créer le compte utilisateur
- L'assigner au bon groupe / à la bonne coop
- S'assurer que son profil sera correctement associé à un `user_ref1` via la structure des groupes Kizeo

## Étape 2 — Synchroniser `app.kizeo_users`

Dans Kizeo Forms, ouvrir le formulaire **"Lancer script python"** (form_id `1108810`) et remplir :

| Champ | Valeur |
|---|---|
| Opération a effectuer | *(opération correspondante)* |
| Script a lancer | `create_kizeo_user_structure.py` |
| BD a mettre à jour ? | `<nom_base>` |
| ID formulaire a mettre à jour ? | *(laisser vide)* |
| ID liste a mettre à jour ? | *(laisser vide)* |

Soumettre → déclenche Make → Flask → le script, qui récupère la liste complète des utilisateurs Kizeo via l'API et fait un upsert dans `app.kizeo_users`.

## Étape 3 — Vérifier

```sql
-- Vérifier que l'utilisateur est présent avec le bon user_ref1
SELECT kizeo_user_id, user_ref1, name, email, is_active
FROM app.kizeo_users
WHERE email = 'nouvel.utilisateur@exemple.com';
```

Si `user_ref1` est `NULL` ou incorrect :
- Vérifier l'assignation groupe/coop dans Kizeo
- Relancer `create_kizeo_user_structure.py`

---

# Cas particuliers

**Utilisateur existant change de coop** : relancer `create_kizeo_user_structure.py` — le upsert met à jour `user_ref1`.

**Utilisateur désactivé** : le champ `is_active` est mis à `false` — les données historiques restent accessibles mais le lien `user_ref1` est préservé.

**Données reçues avant la synchronisation** : si une donnée arrive avant que l'utilisateur soit dans `app.kizeo_users`, l'ingestion échoue. Relancer `create_kizeo_user_structure.py` puis forcer un re-import via `mark_action_kizeo_api_as_unread.py` pour que Make retente l'ingestion.

---

# Checklist

- [ ] Utilisateur créé dans Kizeo et assigné à la bonne coop
- [ ] `create_kizeo_user_structure.py` lancé
- [ ] `app.kizeo_users` vérifié : `user_ref1` correct et `is_active = true`
- [ ] Si données déjà reçues en erreur : `mark_action_kizeo_api_as_unread.py` + re-import

---

# Voir aussi

- [ajout_nouvelle_coop.md](ajout_nouvelle_coop.md) — onboarding complet d'une coop
- [pipeline_kizeo.md](pipeline_kizeo.md) — flux d'ingestion
- [postgresql_schema.md](postgresql_schema.md) — structure de `app.kizeo_users`
- [troubleshooting.md](troubleshooting.md) — erreurs liées à `user_ref1`
