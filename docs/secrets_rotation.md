# Rotation sécurisée du secret Make → Flask (X-Auth-Key)
## Architecture de production sans downtime, alignée sur les standards industriels

---

## 1. Problème initial

Le système Make → Flask repose sur une authentification par header HTTP :

    X-Auth-Key: <secret>

Make appelle le serveur Flask via des requêtes HTTP POST (modules HTTP legacy).
Flask accepte ou rejette la requête selon la valeur du header.

Dans une architecture naïve :
- la clé est stockée dans une variable d’environnement
- ou directement dans Make
- ou hardcodée dans Flask

Ce modèle est dangereux car :
- il empêche toute rotation automatique
- il force un redéploiement ou un redémarrage lors d’un changement
- il crée un risque de fuite ou de désynchronisation
- il entraîne du downtime lors d’un changement de clé

L’objectif était donc de mettre en place une rotation de secrets :
- automatique
- sécurisée
- traçable
- sans interruption de service

---

## 2. Architecture cible

Le flux réel mis en place est le suivant :

    1Password → Script serveur (Windows) → Make (Data Store) → Flask

1Password est la seule source de vérité.
Flask ne parle jamais directement à 1Password ni à Make.
Make ne connaît que la clé courante.

---

## 3. Rôle de 1Password (Vault d’entreprise)

1Password Business est utilisé comme coffre-fort central.

Vault : `INFRA - PROD`

Items dans le vault `INFRA - PROD` :

- `MAKE_TO_FLASK_AUTH` — clé utilisée par Make pour appeler Flask (le secret qui tourne)
- `MAKE_API_TOKEN` — token API permettant au serveur de modifier les Data Stores Make

Sur le serveur Windows :
- l’outil `op.exe` (1Password CLI) est installé à `C:\Program Files\1Password CLI\op.exe`
- l’authentification se fait via Service Account token (commence par `ops_`)
- ce token est stocké dans les **variables d’environnement système Windows** (scope Machine) sous le nom `OP_SERVICE_ACCOUNT_TOKEN` — plus robuste que le Credential Manager (qui peut être effacé lors d’une mise à jour Windows ou d’un reset de profil)
- aucun secret n’est présent dans `.env` ou dans le code source

---

## 4. Script de rotation (orchestrateur)

Un script Python dédié est responsable de toute la rotation.

Chemin :
    C:\srv\flaskapp\scripts\rotate_make_to_flask_auth.py

Ce script est exécuté automatiquement par Windows Task Scheduler (par exemple chaque nuit).

Ce script joue le rôle équivalent à :
- un Vault Agent
- une Lambda de rotation AWS
- un CronJob Kubernetes

Il est le seul composant qui parle à la fois à 1Password et à Make.

---

## 5. Fonctionnement exact de la rotation

À chaque exécution :

1) Le script lit la clé actuelle MAKE_TO_FLASK_AUTH depuis 1Password.  
2) Il demande à 1Password de générer une nouvelle clé sécurisée.  
3) Il relit cette nouvelle clé depuis 1Password.  
4) Il lit le token API Make (MAKE_API_TOKEN).  
5) Il appelle l’API Make pour mettre à jour le Data Store :
   
   PATCH https://us2.make.com/api/v2/data-stores/68962/data/flask_auth_key  
   Body :
   { "value": "<nouvelle clé>" }

6) Il écrit atomiquement le fichier de synchronisation Flask (tmp + rename) :
   - la clé courante
   - la clé précédente
   - la date d’expiration de la clé précédente (now + 30 min)

Le chemin du fichier est défini par la variable d’environnement `MAKE_AUTH_FILE_PATH`.

---

## 6. Fichier de synchronisation pour Flask

Chemin : défini par `MAKE_AUTH_FILE_PATH` (variable d'environnement).

Format :
{
  "current": "<nouvelle clé>",
  "previous": "<ancienne clé>",
  "previous_expires_at": "<date ISO-8601 America/Montreal>"
}

previous_expires_at est calculé comme :
    now + 30 minutes

Ce fichier remplace les secrets en mémoire et les variables d’environnement.

---

## 7. Rôle de Make

Make utilise un Data Store nommé `runtime_secrets`.
La clé `flask_auth_key` contient toujours la clé courante.

Les scénarios Make :
- lisent ce Data Store
- injectent `data.value` dans le header X-Auth-Key

Make ne connaît jamais :
- la clé précédente
- la fenêtre de grâce
- la logique de validation

Ce modèle correspond aux pratiques utilisées dans les pipelines CI/CD et SaaS.

---

## 8. Rôle de Flask

Flask ne contient aucune clé secrète.
Il ne lit aucune variable d’environnement pour l’authentification.

Il lit uniquement le fichier défini par `MAKE_AUTH_FILE_PATH`.

Règles de validation :

- Si X-Auth-Key == current → accepté  
- Si X-Auth-Key == previous ET maintenant < previous_expires_at → accepté  
- Sinon → refusé (401)

Le fichier est relu automatiquement lorsqu’il change.
Si le fichier est absent ou invalide, Flask refuse de démarrer.

---

## 9. Observabilité et audit

Chaque requête est loggée avec :
- request_id
- headers redacted
- script demandé

Les refus sont visibles, corrélés et auditables.
Aucune clé n’apparaît jamais en clair.

---

## 10. Résumé

| Composant | Rôle |
|---|---|
| 1Password | Source de vérité — génère et stocke `MAKE_TO_FLASK_AUTH` |
| Variable système Windows (`OP_SERVICE_ACCOUNT_TOKEN`) | Token Service Account 1Password — scope Machine, permanent |
| `rotate_make_to_flask_auth.py` | Orchestre la rotation (Task Scheduler, quotidien) |
| Make Data Store | Reçoit la nouvelle clé via PATCH API |
| `MAKE_AUTH_FILE_PATH` | Chemin vers `make_auth.json` — variable système Windows, scope Machine |
| Flask | Valide `X-Auth-Key` sans jamais parler à 1Password |

---

## 11. Dépannage — rotation cassée silencieusement

### Symptôme

Le log `logs/rotate_make_to_flask_auth.log` affiche chaque nuit :
```
[ERROR] Credential Manager: token introuvable ou illisible (OP_SERVICE_ACCOUNT_TOKEN_ROTATION).
DETAIL: (1168, 'CredRead', 'Élément introuvable.')
```

### Pourquoi les requêtes Make continuent de fonctionner

Flask valide `X-Auth-Key == current` sans aucune date d'expiration sur `current`. Si la rotation s'arrête, `make_auth.json` et le Data Store Make restent figés sur la même clé — tout fonctionne indéfiniment, mais la clé ne tourne plus.

`previous_expires_at` dans `make_auth.json` concerne uniquement l'ancienne clé (fenêtre de grâce 30 min) — pas la clé courante.

### Cause probable

Les variables d'environnement système ont été effacées (Windows Update, reset de profil, migration serveur, changement de compte Task Scheduler).

### Fix

Vérifier quelles variables système sont présentes :
```powershell
echo $env:OP_SERVICE_ACCOUNT_TOKEN
echo $env:MAKE_AUTH_FILE_PATH
echo $env:CHLOROFILE_ENV_PATH
```

Recréer les variables manquantes (PowerShell **admin**) :
```powershell
# OP_SERVICE_ACCOUNT_TOKEN (token 1Password, commence par ops_)
$token = Read-Host "Colle ton token ops_"
[System.Environment]::SetEnvironmentVariable("OP_SERVICE_ACCOUNT_TOKEN", $token, "Machine")

# MAKE_AUTH_FILE_PATH et CHLOROFILE_ENV_PATH si nécessaire
[System.Environment]::SetEnvironmentVariable("MAKE_AUTH_FILE_PATH", "C:\...\make_auth.json", "Machine")
[System.Environment]::SetEnvironmentVariable("CHLOROFILE_ENV_PATH", "C:\...\chlorofile.env", "Machine")
```

Tester manuellement dans un **nouveau terminal** :
```powershell
C:\srv\flaskapp\.venv\Scripts\python.exe C:\srv\flaskapp\scripts\rotate_make_to_flask_auth.py
```

Résultat attendu : 7 lignes `[INFO]` terminant par `Rotation job completed successfully`.

---

## 12. Configuration Task Scheduler

Tâche : **Rotate Make→Flask Auth Key**

| Paramètre | Valeur |
|---|---|
| Programme/script | `C:\srv\flaskapp\.venv\Scripts\python.exe` |
| Arguments | `C:\srv\flaskapp\scripts\rotate_make_to_flask_auth.py` |
| Commencer dans | `C:\srv\flaskapp\scripts` |
| Déclencheur | Quotidien à minuit |

**Important :** le Python doit pointer vers le **venv** (`\.venv\Scripts\python.exe`) et non le Python système (`C:\Program Files\Python313\python.exe`). Le venv contient `tzdata`, `win32cred`, et toutes les dépendances requises.

Les variables d'environnement système (scope Machine) sont automatiquement héritées — pas besoin de les redéfinir dans la tâche.
