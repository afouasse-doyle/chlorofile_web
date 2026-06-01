# 🛠️ Troubleshooting & Diagnostic
*Guide de résolution des problèmes pour le pipeline Kizeo → Flask → PostgreSQL*

Ce document regroupe :
- les erreurs fréquentes,
- leurs causes probables,
- les étapes de diagnostic,
- et les solutions concrètes.

Il couvre :
- l’API Flask,
- les scripts Python,
- l’API Kizeo,
- PostgreSQL,
- les exports,
- les listes,
- Make,
- l’ODBC.

---

# 1. Problèmes côté API Flask

## 1.1. Erreur : `401 Unauthorized` / `Invalid authentication key`

**Cause probable :**
- Mauvaise valeur dans l’en‑tête `X-Auth-Key`
- Clé dans Make ≠ clé courante dans `make_auth.json`
- Fenêtre de grâce expirée (> 30 min après rotation)

**Diagnostic :**
1. Vérifier Make → HTTP module (valeur `X-Auth-Key`)
2. Vérifier `make_auth.json` (champs `current` et `previous`)
3. Vérifier que la dernière rotation (`rotate_make_to_flask_auth.py`) s’est bien exécutée

**Solution :**
- Relancer manuellement `rotate_make_to_flask_auth.py` si besoin
- Vérifier le Make Data Store — il doit contenir la clé `current` du JSON
- Redémarrer le service Flask (NSSM) si `make_auth.json` a été modifié manuellement

---

## 1.2. Erreur : `Script not found` ou `FileNotFoundError`

**Cause :**
- `X-Script-Name` mal écrit
- Le fichier n’existe pas dans `scripts/`
- Le script a été renommé mais Make n’a pas été mis à jour

**Diagnostic :**
- Lister le dossier `scripts/`
- Comparer avec Make

**Solution :**
- Corriger `X-Script-Name`

---

## 1.3. Erreur : `Exception: <stack trace>` ou timeout

**Causes possibles :**
- script en boucle
- blocage réseau
- script lent (Excel, JSON volumineux)
- appel PostgreSQL trop long

**Diagnostic :**
1. Lire les logs Flask  
2. Lire le logger du script (affiché dans les logs)  
3. Vérifier la charge CPU/mémoire

**Solutions possibles :**
- optimiser les scripts
- ajouter des timeouts HTTP
- réduire les logs trop volumineux
- séparer les opérations trop lourdes en plusieurs étapes

---

# 2. Problèmes côté API Kizeo

## 2.1. Erreur HTTP Kizeo : `404 Not Found`

**Causes :**
- `form_id` ou `data_id` invalide
- enregistrement supprimé dans Kizeo
- mauvais export (`export_id` ne correspond pas au `form_id`)

**Diagnostic :**
- Tester l’URL avec `curl`
- Vérifier dans Kizeo :
  - le formulaire existe
  - l’enregistrement existe

**Solution :**
- Corriger `form_id` / `data_id`
- Resynchroniser le catalogue (`sync_kizeo_catalog.py`) pour s'assurer que `app.kizeo_form_exports` est à jour

---

## 2.2. Erreur Kizeo : `429 Too Many Requests`

**Cause :**
- Trop de requêtes en peu de temps

**Diagnostic :**
- Survient souvent lors de batch massifs

**Solutions :**
- Ajouter des `sleep()` progressifs
- Diviser les batchs
- Utiliser le mode pagination intégré dans les scripts

---

## 2.3. Erreur Kizeo : `401 Unauthorized`

**Causes :**
- Token expiré ou révoqué
- Token mal configuré dans `.env`

**Solution :**
- Regénérer un token dans Kizeo
- Mettre `.env` à jour
- Redémarrer le service Flask

---

# 3. Problèmes côté PostgreSQL

## 3.0. Erreur : `user_ref1` NULL ou donnée rejetée après soumission Kizeo

**Cause :**
- Un utilisateur Kizeo a soumis une donnée mais n'existe pas encore dans `app.kizeo_users`
- `user_ref1` ne peut pas être résolu → la donnée est rejetée ou écrite sans coop

**Diagnostic :**
```sql
-- Vérifier si l'utilisateur est présent
SELECT * FROM app.kizeo_users WHERE kizeo_user_id = <_user_id>;
```

**Solution :**
1. Lancer `create_kizeo_user_structure.py` pour synchroniser `app.kizeo_users`
2. Vérifier que `user_ref1` est correct après sync
3. Relancer l'ingestion via `mark_action_kizeo_api_as_unread.py` pour que Make retente

Voir [ajout_utilisateur_kizeo.md](ajout_utilisateur_kizeo.md) pour la procédure complète.

---

## 3.1. Erreur : `permission denied`

**Causes :**
- rôle applicatif mal configuré
- RLS active mais variable coop non définie
- utilisateur ODBC essayant d’écrire

**Diagnostic :**
- Tester la requête SQL avec le même utilisateur

**Solution :**
- Ajuster les rôles
- Vérifier RLS (`app.current_coop()`)

---

## 3.2. Erreur : `relation does not exist`

**Causes :**
- le schéma n’a pas été généré (`kizeo_schema_builder.py` non exécuté)
- le `form_id` ne correspond à aucune table

**Solution :**
- lancer `kizeo_schema_builder.py` avec le `form_id` correct

---

## 3.3. Erreur : `duplicate key value violates unique constraint`

**Cause :**
- script qui insère sans UPSERT
- modification d’une clé primaire côté Kizeo

**Solution :**
- s’assurer que le script utilise :  
  `ON CONFLICT (_id) DO UPDATE`

---

# 4. Problèmes côté exports Excel/PDF

## 4.1. Problème : export Excel fonctionne mais pas le PDF

**Causes possibles :**
- mauvais export_id
- export PDF non configuré dans Kizeo
- erreur dans le chemin `/pdf`

**Solution :**
- Resynchroniser le catalogue (`sync_kizeo_catalog.py`) — il alimente `app.kizeo_form_exports`
- Vérifier les colonnes `name_excel` / `name_pdf` dans `app.kizeo_form_exports` pour le `form_id` concerné

---

## 4.2. Fichiers écrasés ou non nommés correctement

**Cause :**
- renommage manuel incorrect
- problème dans `name_builder.py`

**Diagnostic :**
1. Vérifier que `Content-Disposition` contient le nom attendu  
2. Vérifier que `name_builder` n’ajoute rien

**Solution :**
- laisser le nom réel fourni par Kizeo

---

## 4.3. Export envoyé dans le mauvais dossier

**Cause :**
- mauvais `user_ref1`
- erreur dans la table `app.coops`
- `year_suffix` incorrect

**Solution :**
- vérifier la logique dans `name_builder.py`
- vérifier les dossiers créés automatiquement

---

# 5. Problèmes côté listes Kizeo

## 5.1. Champs manquants ou mauvais format dans Data Manuelle

**Cause :**
- colonnes différentes selon les coops
- fichiers Excel modifiés par accident

**Diagnostic :**
- logs de `create_kizeo_lists_excel.py`
- comparer les colonnes à la structure attendue

**Solution :**
- uniformiser les colonnes
- corriger le fichier Excel fautif

---

## 5.2. Upload JSON rejeté par Kizeo

**Causes :**
- `list_id` incorrect
- JSON invalide
- champs obligatoires manquants

**Solution :**
- vérifier le JSON généré dans `UPLOAD_KIZEO_JSON_DIR` (UE, parcelles, etc.)
- retracer via les logs de `upload_lists_to_kizeo.py`

---

# 6. Problèmes côté Make

## 6.1. Erreurs sporadiques dans Make

**Causes :**
- timeout Make trop court
- instabilité du réseau
- nombres excessif de runs parallèles

**Solutions :**
- augmenter le timeout
- séparer les scénarios
- utiliser des files d’attente

---

## 6.2. Payload Make incorrect ou incomplet

**Diagnostic :**
- comparer le payload réel dans les logs Flask
- vérifier les variables dans Make

**Solutions :**
- renvoyer les bons champs :  
  - `form_id`, `data_id`, `export_name`, `year_suffix`, `ue`, etc.

---

# 7. Problèmes côté ODBC

## 7.1. L’utilisateur ODBC ne voit aucune donnée

**Causes :**
- RLS active mais rôle incorrect
- `user_ref1` absent dans les tables
- session PostgreSQL sans `app.user_ref1` définie

**Solutions :**
- vérifier rôle associé
- vérifier existence de `user_ref1`
- tester la fonction `app.current_coop()`

---

## 7.2. Erreur : “Permission denied” en lecture

**Cause :**
- rôle ODBC non mappé au schéma du formulaire

**Solution :**
- ajouter :  
  `GRANT USAGE ON SCHEMA "880205" TO coop_ro_abifor;`  
  `GRANT SELECT ON ALL TABLES IN SCHEMA "880205" TO coop_ro_abifor;`

---

# 8. Problèmes Windows / infrastructure

## 8.1. Le service Flask ne démarre pas (NSSM)

**Causes :**
- mauvais chemin vers Python
- `.env` non accessible
- droits insuffisants

**Solution :**
- tester le lancement manuel :
  ```bash
  C:\srv\flaskapp\.venv\Scripts\python.exe run_flask_server.py
  ```

---

## 8.2. Le script Python fonctionne en CLI mais pas via Flask

**Cause :**
- variables d’environnement différentes

**Diagnostic :**
- ajouter un log dans le script :
  ```python
  logger.info(f"ENV: {os.getenv('PG_DB')}")
  ```

**Solution :**
- synchroniser `.env` serveur ↔ `.env` local

---

# 9. Outils utiles de debug

- `print(payload)` → à éviter, utiliser `logger.info()`
- `curl` pour tester `/run`
- `psql` ou DBeaver pour tester SQL
- `python -m json.tool` pour valider les JSON
- `MERMAID` pour visualiser le pipeline

---

# 10. Voir aussi

- [api_endpoints.md](api_endpoints.md) — endpoints Flask et payloads
- [security_env.md](security_env.md) — secrets et variables d'environnement
- [secrets_rotation.md](secrets_rotation.md) — rotation X-Auth-Key
- [scripts_overview.md](scripts_overview.md) — tous les scripts
- [postgresql_schema.md](postgresql_schema.md) — schéma de la base
- [architecture.md](architecture.md) — vue globale du système

