# 🔐 Sécurité & Variables d’environnement
*Gestion des mots de passe, tokens et accès dans la plateforme Kizeo → Flask → PostgreSQL*

Ce document explique comment :
- stocker les secrets (tokens Kizeo, mots de passe PostgreSQL, clés API),
- configurer correctement le fichier `.env`,
- limiter les accès au serveur Flask,
- sécuriser les connexions PostgreSQL,
- gérer les logs sans fuite d’informations sensibles.

Il sert de guide pour toute personne qui administre ou reprend l’infrastructure.

---

# 1. Principes de base

1. **Aucun secret ne doit être hardcodé dans le code Python**  
   → Pas de mot de passe directement dans les scripts.

2. **Utiliser systématiquement le fichier `.env`** pour :  
   - les identifiants PostgreSQL,  
   - le token Kizeo,  
   - la clé d’authentification Flask (`X-Auth-Key`),  
   - les chemins sensibles.

3. **Limiter les accès réseau** :  
   - au serveur Flask (via firewall / FQDN / IPs Make),  
   - à PostgreSQL (via `pg_hba.conf` + SSL).

4. **Utiliser des rôles PostgreSQL séparés** :  
   - rôle applicatif (scripts Python),  
   - rôles read-only ODBC par coop.  

5. **Tracer sans exposer** :  
   - ne jamais logger les mots de passe ou tokens en clair,  
   - éviter de logguer l’intégralité des payloads contenant des secrets.

---

# 2. Fichier `.env`

Le fichier `.env` est stocké **hors du répertoire projet** — intentionnellement séparé du dépôt Git. Il n’existe pas à la racine de `c:\srv\flaskapp\`. Cette séparation garantit qu’aucun secret ne peut être versionné accidentellement.

La liste complète des variables avec descriptions est dans [env_variables.md](env_variables.md).

## 2.1. Chargement côté scripts

Les scripts chargent les variables d’environnement de deux façons possibles :

1. **Mode “dispatcher” (production)**  
   - NSSM configure le service avec les variables d’environnement injectées directement,
   - les scripts les lisent via `os.getenv()` — aucun `load_dotenv()` nécessaire.

2. **Mode “standalone / debug”**  
   - Le script charge le `.env` externe via la variable système `CHLOROFILE_ENV_PATH` :  
     ```python
     from dotenv import load_dotenv
     _ep = os.environ.get(“CHLOROFILE_ENV_PATH”)
     if not _ep:
         raise SystemExit(“CHLOROFILE_ENV_PATH non définie”)
     load_dotenv(_ep)
     ```
   - `CHLOROFILE_ENV_PATH` est une variable système Windows pointant vers `C:\srv\secrets\Chlorofile\.env`.

Il est important de **conserver cette double logique** pour pouvoir :
- tester les scripts en local sans toucher à la configuration NSSM,
- les exécuter en production via Flask sans modifier le code.

---

# 3. Secrets principaux

## 3.1. Token Kizeo (`KIZEO_TOKEN`)

- Sert à appeler l’API Kizeo (`rest/v3`).
- Ne jamais l’écrire dans les logs.
- Ne jamais l’envoyer par courriel / Teams / chat en clair.
- Si possible :  
  - le stocker dans un gestionnaire de mots de passe (KeePass / Bitwarden / 1Password, etc.),  
  - ne mettre dans `.env` que la copie nécessaire au serveur.

Si le token fuit ou est compromis → le régénérer dans Kizeo et mettre à jour le `.env`.

---

## 3.2. Accès PostgreSQL (`PG_USER`, `PG_PASSWORD`)

- Ce compte doit être **limité** à ce dont les scripts ont besoin :  
  - création de schémas `form_id`,  
  - création de tables dans ces schémas,  
  - accès en lecture / écriture dans `app.*`,  
  - pas nécessairement superuser.

- Le mot de passe doit :  
  - être long et complexe,  
  - être stocké dans un coffre (gestionnaire de mots de passe),  
  - être changé périodiquement / en cas de doute.

- Les utilisateurs ODBC (coops) doivent avoir **leurs propres comptes** :  
  - `abifor_odbc`, `cfg_odbc`, etc.  
  - accès en lecture seule avec RLS activée.

---

## 3.3. Clé d’authentification Flask (`X-Auth-Key`)

- Transmise dans l’en-tête HTTP `X-Auth-Key` par Make.
- Flask valide via un système **dual-key** (`current` + `previous` avec fenêtre de grâce de 30 min).
- La clé n’est **pas** dans `.env` — elle est gérée par `rotate_make_to_flask_auth.py` (rotation quotidienne via 1Password).

Voir [secrets_rotation.md](secrets_rotation.md) pour l’architecture complète.

Flux : **1Password** (source de vérité) → script rotation → **Make Data Store** (clé courante) + **`make_auth.json`** (lu par Flask).

---

# 4. Sécurité du serveur Flask

Le serveur Flask est un composant central : il ne doit **pas** être exposé librement sur Internet.

## 4.1. Points clés

- Idéalement, accessible uniquement :
  - depuis Make (IPs / FQDN autorisés),
  - depuis le réseau interne (VPN / LAN).

- Utiliser un reverse proxy (ex : Caddy, Nginx, etc.) avec :
  - HTTPS,
  - limitation des origines / hosts,
  - éventuellement authentification supplémentaire (basic auth, certificat client…).

- Désactiver les endpoints inutiles ou de debug en production :
  - pas de `/shutdown` accessible,
  - pas de debugger Flask activé.

## 4.2. Logs Flask

- Les logs doivent contenir :
  - ID de requête (correlation ID),
  - script appelé,
  - durée d’exécution,
  - messages d’erreur génériques.

- Les logs **ne doivent pas** contenir :
  - les mots de passe,
  - le token Kizeo,
  - les payloads complets si ceux-ci contiennent des secrets (ou les masquer).

---

# 5. Sécurité PostgreSQL

## 5.1. `pg_hba.conf`

La configuration `pg_hba.conf` doit :
- autoriser seulement les IPs / réseaux nécessaires (serveur Flask, postes admin, etc.),
- forcer l’utilisation de `hostssl` lorsque possible,
- utiliser des méthodes d’authentification fortes (`scram-sha-256`).

Exemple (à adapter) :

```conf
# Accès depuis le serveur Flask
hostssl  yourdb   your_app_user   10.0.0.10/32    scram-sha-256

# Accès ODBC ABIFOR
hostssl  yourdb   abifor_odbc     10.0.0.0/24     scram-sha-256
```

## 5.2. Rôles & RLS

Voir `postgresql_schema.md` pour les détails, mais en résumé :

- l’utilisateur applicatif utilise **tous les schémas** (création / écriture),
- les utilisateurs ODBC ont des droits en lecture seule,
- la RLS s’assure qu’une coop ne voit que ses données (`user_ref1`).

---

# 6. Gestion des logs

Les logs sont essentiels, mais peuvent aussi révéler des informations sensibles.

**Bonnes pratiques :**

- Ne jamais logger les contenus de `.env`.
- Ne pas logger les mots de passe ni les tokens.
- Pour les payloads :
  - logguer seulement les champs utiles au debug (form_id, data_id, user_id, etc.),
  - éviter les dumps complets quand ce n’est pas nécessaire.

- Prévoir une rotation des logs (taille / durée) pour éviter de remplir le disque.
- Sauvegarder les logs sensibles dans un endroit protégé.

---

# 7. Mots de passe & gestionnaires de secrets

Les mots de passe et tokens (PostgreSQL, Kizeo, clés Graph, etc.) doivent être :

1. Jamais partagés en clair (email, messagerie non chiffrée…).
2. Renouvelés régulièrement ou lorsqu’un doute existe (machine compromise, départ d’un employé, etc.).
3. Distribués aux développeurs selon un workflow à définir — contacter l’administrateur.

> **1Password** est utilisé **uniquement** pour la rotation automatique de la clé `X-Auth-Key` (Flask ↔ Make) via `rotate_make_to_flask_auth.py`. Ce n’est pas le coffre général des secrets de l’infrastructure.

Le `.env` sur le serveur doit être protégé par :

- stockage hors du répertoire projet et hors du dépôt Git,
- permissions NTFS restreintes (lecture uniquement pour le compte de service NSSM),
- sauvegardes chiffrées si nécessaire.

---

# 8. Cas particuliers : tests & environnements multiples

Pour éviter les erreurs entre environnements :

- Utiliser des `.env` distincts :  
  - `.env.test` pour l’environnement de test,  
  - `.env.prod` pour la production.

- Le script de lancement (ou NSSM) doit pointer vers le bon fichier.  
- Ne jamais connecter un script de test à la base de production par erreur.

Exemple simple en Python :

```python
import os
from dotenv import load_dotenv

env_file = os.getenv("ENV_FILE", ".env")
load_dotenv(env_file)
```

Puis lancer le script avec :

```bash
set ENV_FILE=.env.test
python run_flask_server.py
```

---

# 9. Checklist sécurité rapide

Avant de considérer l’infrastructure “ok” côté sécurité :

- [ ] `.env` stocké hors du répertoire projet (hors `c:\srv\flaskapp\`)
- [ ] `.env` absent du dépôt Git — vérifier `.gitignore`
- [ ] `.env` protégé en lecture NTFS (compte de service uniquement)
- [ ] tous les secrets sont dans `.env` (pas dans le code)  
- [ ] Rotation `X-Auth-Key` active (`rotate_make_to_flask_auth.py` via Task Scheduler)  
- [ ] token Kizeo sécurisé (coffre, `.env` uniquement sur le serveur)  
- [ ] `pg_hba.conf` restreint aux IPs nécessaires  
- [ ] SSL activé pour PostgreSQL (`PG_SSLMODE=require`)  
- [ ] rôles ODBC avec droits limités + RLS active  
- [ ] logs ne contiennent pas de secrets  
- [ ] pas d’endpoint Flask de debug exposé en production  

---

# 10. Voir aussi

- [env_variables.md](env_variables.md) — référence complète de toutes les variables `.env`
- [secrets_rotation.md](secrets_rotation.md) — rotation automatique de la clé X-Auth-Key
- [postgresql_schema.md](postgresql_schema.md) — structure de la base & RLS
- [architecture.md](architecture.md) — vue globale du système
