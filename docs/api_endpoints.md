# API Flask – Endpoints exposés
*Interface HTTP entre Make et le serveur Flask (dispatcher de scripts)*

Ce document décrit les endpoints principaux exposés par `run_flask_server.py` et la manière correcte de les appeler.

Il s’adresse à toute personne qui :
- configure des scénarios Make,
- veut tester manuellement les scripts via HTTP,
- ou reprend le serveur Flask.

---

# 1. Vue d’ensemble

Le serveur Flask joue le rôle de **dispatcher** entre :
- les appels HTTP (Make, tests manuels),
- et les scripts Python présents dans le dossier `scripts/`.

Endpoints principaux :

| Méthode | URL       | Rôle                                  |
|---------|-----------|----------------------------------------|
| `GET`   | `/health` | Vérifier que le serveur est en ligne  |
| `POST`  | `/run`    | Exécuter un script Python donné       |

D’autres endpoints internes ou de debug peuvent exister, mais **ne doivent pas être exposés en production**.

---

# 2. Sécurité générale de l’API

Deux niveaux de sécurité doivent être pris en compte :

1. **Accès réseau**  
   - Firewall / reverse proxy (Caddy, Nginx, etc.)  
   - Idéalement, seules les IPs / services autorisés (Make, réseau interne) peuvent joindre l’API.

2. **Clé d’authentification applicative**  
   - Header obligatoire : `X-Auth-Key`  
   - La clé courante est gérée par le système de rotation quotidienne (`rotate_make_to_flask_auth.py`) — voir [secrets_rotation.md](secrets_rotation.md).  
   - Flask valide via un fichier dual-key (`current` + `previous` avec fenêtre de grâce). Si la clé ne correspond pas → 401.

**Important :**  
La clé ne doit *jamais* être loggée ni partagée en clair.

---

# 3. Endpoint `/health`

## 3.1. Description

**Méthode :** `GET`  
**URL :** `/health`

Permet de vérifier que le serveur répond correctement (monitoring, tests rapides).

## 3.2. Exemple d’appel

```bash
curl -X GET "https://ton-serveur-flask/health"
```

## 3.3. Réponse typique

```json
{
  "status": "ok",
  "message": "flask server is running"
}
```

Aucune authentification spécifique n’est nécessaire pour cet endpoint (à adapter selon ta politique de sécurité).

---

# 4. Endpoint `/run`

## 4.1. Description

**Méthode :** `POST`  
**URL :** `/run`

C’est l’endpoint principal pour appeler un script Python du dossier `scripts/`.

Le serveur :

1. Valide `X-Auth-Key` (obligatoire).  
2. Lit `X-Script-Name` pour savoir quel script charger.  
3. Charge dynamiquement `scripts/<X-Script-Name>`.  
4. Appelle sa fonction :

    ```python
    def handle(payload: dict, logger) -> dict:
        ...
    ```

5. Retourne la réponse du script sous forme de JSON.

## 4.2. Headers requis

- `Content-Type: application/json`
- `X-Auth-Key: <clé partagée définie dans .env>`
- `X-Script-Name: <nom_du_script.py>`

Exemples de valeurs pour `X-Script-Name` (scripts avec `handle()`) :

- `fetch_data_kizeo_api.py`
- `name_builder.py`
- `download_kizeo_file.py`
- `register_kizeo_export.py`
- `kizeo_schema_builder.py`
- `sync_kizeo_catalog.py`
- `ddif_name_builder.py`
- `upsert_data_manuelle_db.py`
- `create_kizeo_lists_excel.py`
- `mark_action_kizeo_api_as_unread.py`
- etc.

> `create_kizeo_lists_json.py` et `upload_lists_to_kizeo.py` sont des subprocess uniquement — ils n'ont pas de `handle()` et ne peuvent pas être appelés via `/run`.

Le nom doit correspondre **exactement** au fichier présent dans `scripts/`.

## 4.3. Corps de la requête (`payload`)

Le corps est un JSON transmis tel quel au script sous forme de `payload`.  
Sa structure dépend du script appelé.

Exemples :

### 4.3.1. Exemple pour `fetch_data_kizeo_api.py`

```json
{
  "form_id": "880205",
  "data_id": "177314594",
  "bd": "chlorofile2"
}
```

Pour une suppression Kizeo, ajouter `"deleted": true` — le script skipera le GET API et traitera le tombstone.

### 4.3.2. Exemple pour `name_builder.py` (export Excel/PDF)

```json
{
  "form_id": "880205",
  "data_id": "177314594",
  "export_name": "Formulaire de nettoiement avant traitement BSLG",
  "user_id": "562703",
  "bd": "chlorofile2",
  "year_suffix": "2025-2026",
  "ue": "2023-11161_-ELS3-502",
  "region": "01",
  "export_type": "excel"
}
```

### 4.3.3. Exemple pour `sync_kizeo_catalog.py`

```json
{
  "bd": "chlorofile2",
  "form_id": "880205"
}
```

Sans `form_id` → synchronisation globale (toutes les forms et listes).

Le script est responsable de :

- valider le payload,  
- lever des erreurs claires en cas de champ manquant,  
- retourner un objet JSON structuré.

## 4.4. Exemple d’appel `curl` complet

```bash
curl -X POST "https://ton-serveur-flask/run" \
  -H "Content-Type: application/json" \
  -H "X-Auth-Key: TON_SECRET" \
  -H "X-Script-Name: fetch_data_kizeo_api.py" \
  -d '{"form_id": "880205", "data_id": "177314594", "bd": "chlorofile2"}'
```

## 4.5. Exemple de réponse typique

Succès :

```json
{
  "status": "success",
  "script": "fetch_data_kizeo_api.py",
  "details": {
    "form_id": "880205",
    "processed_count": 1,
    "run_dir": "C:/srv/flaskapp/runs/run_880205_2025-11-10_141500"
  }
}
```

Erreur (exemple) :

```json
{
  "status": "error",
  "script": "fetch_data_kizeo_api.py",
  "message": "Missing required field: form_id"
}
```

La structure exacte dépend de l’implémentation de tes scripts, mais l’idée est de rester cohérent :  
- `status` = `success` / `error`  
- `script` = nom du script exécuté  
- `details` ou `message` = informations utiles au debug  

---

# 5. Comportement des scripts côté serveur

Lorsqu’un script est appelé par `/run`, le serveur :

1. Crée un **logger** spécifique à la requête (avec un ID de corrélation).  
2. Exécute `handle(payload, logger)`.  
3. Catch toutes les exceptions non gérées pour :  
   - retourner une erreur propre côté API,  
   - logger la stack trace côté serveur.

Recommandations pour les scripts :

- Ne pas faire de `print()` brut, mais utiliser le `logger`.  
- Toujours valider les champs obligatoires du `payload`.  
- En cas d’erreur métier (ex. `form_id` inconnu), lever une exception claire ou retourner un `status: "error"` explicite.  

---

# 6. Intégration avec Make

Dans Make, un scénario type qui appelle `/run` contiendra :

- **Module HTTP > Make a request**  
- **URL** : `https://ton-serveur-flask/run`  
- **Méthode** : `POST`  
- **Headers** :  
  - `Content-Type: application/json`  
  - `X-Auth-Key = AUTH_ENV_KEY`  
  - `X-Script-Name = nom_du_script.py`  
- **Body type** : JSON  
- **Request content** : les champs du `payload`

Exemple de body dans Make (mode RAW) :

```json
{
  "form_id": "{{2.form_id}}",
  "data_id": "{{2.data_id}}",
  "bd": "prod",
  "year_suffix": "2025-2026"
}
```

Les variables entre `{{ }}` sont extraites d’un module précédent (webhook Kizeo, etc.).

---

# 7. Bonnes pratiques API

- Toujours tester un nouveau script en local (CLI) avant de l’exposer via `/run`.  
- Logger suffisamment d’informations côté serveur pour comprendre ce qui se passe, mais sans jamais inclure de secrets.  
- Documenter pour chaque script les champs attendus dans le `payload` — la référence est [payloads_by_script.md](payloads_by_script.md).

---

# 8. Voir aussi

- [payloads_by_script.md](payloads_by_script.md) — référence complète des champs de payload par script
- [scripts_overview.md](scripts_overview.md) — rôle détaillé de chaque script
- [secrets_rotation.md](secrets_rotation.md) — système de rotation de la clé X-Auth-Key
- [security_env.md](security_env.md) — gestion des variables d’environnement
- [architecture.md](architecture.md) — vue globale de l’infrastructure
- [pipeline_kizeo.md](pipeline_kizeo.md) — pipeline d’ingestion des formulaires
- [pipeline_exports.md](pipeline_exports.md) — pipeline des exports PDF/Excel
