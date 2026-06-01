# DDIF Export Engine

Système d'export **DDIF (.DBF FoxPro)** piloté par **packs** *(année /
formulaire / région)*.

------------------------------------------------------------------------

## 1️⃣ 🎯 Objectif du système

Le moteur DDIF génère automatiquement un lot de **7 à 10 fichiers `.DBF`
(FoxPro / Visual FoxPro style)** strictement formatés à partir des données
**PostgreSQL**, **sans Excel / sans COM** et **sans conversion
`.XLSX`**.

**Déclenchement :**\
`Kizeo → Make → API Flask → ddif_name_builder → build_ddif_exports`

Le moteur doit :

-   Identifier :
    -   `year_suffix`
    -   `form_name`
    -   `region`
    -   `ue`
    -   paramètres runtime (`nb_0`, `mtm`, `user_ref1`, `id_projet`,
        etc.)
-   Appliquer les règles propres à la région (via le pack, pas via
    Python)
-   Générer des `.DBF` conformes aux gabarits officiels
-   Uploader vers SharePoint (Microsoft Graph)
-   Être **100% reproductible** par année (**packs figés**)

------------------------------------------------------------------------

## 2️⃣ 🧠 Philosophie d'architecture

Séparation stricte des responsabilités :

  ---------------------------------------------------------------------
  Élément                            Rôle
  ---------------------------------- ----------------------------------
  **Templates DBF (FoxPro)**         Définissent les **colonnes
                                     finales** (source de vérité)

  **SQL (par feuille)**              Produit les **valeurs finales**

  **Python**                         Orchestre, copie, écrit, upload
                                     *(aucune logique métier)*

  **Pack régional**                  Définit les règles (SQL + config)

  **Payload utilisateur**            Fournit les paramètres runtime
  ---------------------------------------------------------------------

**Principe fondamental :**

✅ Le code Python est unique\
✅ La configuration change par pack\
✅ **1 feuille = 1 fichier SQL**\
✅ **Toute la logique métier vit en SQL**\
✅ `Source = #"form_id"` correspond toujours à
`FROM p_form_id.p_form_id`

Interdit :

❌ Aucune logique régionale en Python\
❌ Aucun `form_id` hardcodé\
❌ Aucune manipulation Excel COM\
❌ Aucune conversion `.XLS → .XLSX`

------------------------------------------------------------------------

## 3️⃣ 📁 Structure des packs

Structure :

``` text
ddif/
  2025-2026/
    2025- DEG APT (GIM BSL SLSJ ABIT MAU CN)/
      BSL/
        config.yaml
        templates/
          INFO_GEN.DBF
          P_ES_CO.DBF
          SYSTEME.DBF
          MICRO_PL.DBF
          PROJET.DBF
          DNBR_EPC.DBF
          ...
        sql/
          INFO_GEN.sql
          P_ES_CO.sql
          SYSTEME.sql
          MICRO_PL.sql
          PROJET.sql
          DNBR_EPC.sql
          ...
```

### 📄 `templates/`

-   Contient les `.DBF` officiels (FoxPro)
-   Source de vérité des colonnes (headers)
-   Toujours copiés, même si aucune donnée n'est écrite
-   Jamais modifiés par le moteur (on copie puis on écrit dans la copie)

### 🧩 `sql/`

-   **1 fichier SQL par export**
-   Chaque fichier **crée une fonction spécifique au pack**

Convention :

-   `app.ddif_<year_suffix>_<traitement>_<region>_<export>`

Exemple :

-   `app.ddif_2025_2026_degapt_bsl_dnbr_epc`

Avantages :

-   Isolation par région
-   Isolation par année
-   Aucune collision
-   Historique traçable

------------------------------------------------------------------------

### ⚙ `config.yaml` 🔥 (SECTION CONTRACTUELLE OFFICIELLE)

Définit le mapping payload → cfg\
Permet les overrides runtime\
Peut définir des valeurs par défaut runtime\
Est la seule source de vérité pour les valeurs overridables

La SQL peut contenir des valeurs techniques internes par défaut, mais
toute valeur pouvant être overridée doit obligatoirement passer par
`cfg`.

------------------------------------------------------------------------

### 🧠 Principe officiel de gestion des overrides

Il existe **3 types de valeurs** :

1️⃣ Valeur purement SQL (jamais overridable)\
→ définie uniquement dans la SQL.

2️⃣ Valeur avec override possible via payload\
→ la clé doit être déclarée dans `cfg_from_payload`.

3️⃣ Valeur avec default + override possible\
→ default défini dans `cfg_defaults`\
→ override via `cfg_from_payload`.

------------------------------------------------------------------------

### 🧩 Exemple structure contractuelle correcte

``` yaml
version: 1

exports:

  INFO_GEN:
    sql:
      install_file: "sql/INFO_GEN.sql"
      function: "app.ddif_2025_2026_degapt_bsl_info_gen"

    cfg_from_payload:
      nb_0: nb_0
      mtm: mtm
      user_ref1: user_ref1
      id_projet: id_projet
      ind_action_info_gen: ind_action_info_gen

  P_ES_CO:
    sql:
      install_file: "sql/P_ES_CO.sql"
      function: "app.ddif_2025_2026_degapt_bsl_p_es_co"

    cfg_from_payload:
      nb_0: nb_0
      user_ref1: user_ref1
      id_projet: id_projet
      ind_action_p_es_co: ind_action_p_es_co

  SYSTEME:
    sql:
      install_file: "sql/SYSTEME.sql"
      function: "app.ddif_2025_2026_degapt_bsl_systeme"

    cfg_from_payload:
      nb_0: nb_0
      user_ref1: user_ref1
      id_projet: id_projet
      ind_action_systeme: ind_action_systeme
```

------------------------------------------------------------------------

### 🔥 Règles STRICT (config)

-   `id_projet` doit être déclaré dans chaque export qui supporte
    l'override.
-   Chaque export peut avoir son propre `ind_action_<export>`.
-	ind_action_p_es_co existe mais arrive toujours sous la payload ind_action_p_ess_co afin de ne pas dédoubler le tout et en attendant une correction du ministère car p_es_co et p_ess_co ne devraient pas exister, il ne devrait en avoir qu'un seul. 
-   Aucune clé runtime ne doit être lue directement depuis payload dans
    la SQL.
-   La SQL lit uniquement `p_cfg->>'clé'`.
-   Si une clé n'est pas déclarée dans `cfg_from_payload`, elle n'existe
    pas dans `cfg`.
-   Aucun fallback implicite autorisé.
-   Aucune double source de vérité runtime.

------------------------------------------------------------------------

## 4️⃣ 🔄 Flux d'exécution

### Étape 1 --- Réception du payload

``` json
{
  "bd": "chlorofile2",
  "year_suffix": "2025-2026",
  "form_name": "2025- DEG APT (GIM BSL SLSJ ABIT MAU CN)",
  "region": "BSL",
  "ue": "01272_DEGMEC_24251",
  "form_id": "1052897",
  "nb_0": "5",
  "mtm": "6",
  "user_ref1": "FQCF",
  "id_projet": "TESTPROJET",
  "output_dir": "1-Gestion/2025-2026/.../BSL/01272_DEGMEC_24251"
}
```

### Étape 2 --- Résolution du pack

`ddif/<year_suffix>/<form_name>/<region>/`

### Étape 3 --- Lecture du pack

-   `templates/`
-   `config.yaml`
-   `sql/*.sql`

### Étape 4 --- Pour chaque template `.DBF`

-   Lire les headers / champs depuis le template DBF
-   Copier le template
-   Si export SQL configuré :
    -   Construire `cfg` :
        1.  Lire `cfg_defaults`
        2.  Appliquer `cfg_from_payload`
        3.  Injecter uniquement les clés explicitement déclarées
        4.  Aucune clé payload non déclarée ne doit entrer dans `cfg`
        5.  Aucune clé non déclarée ne doit être transmise à la SQL
    -   Installer SQL (CREATE OR REPLACE FUNCTION)
    -   Appeler
        `SELECT * FROM function(year_suffix, region, ue, cfg, form_id)`
    -   Écrire les valeurs dans la copie `.DBF`
-   Upload vers SharePoint (Graph)
-   Résilience : un échec ne casse pas le run

------------------------------------------------------------------------

## 5️⃣ 🧩 Signature SQL standardisée

Toutes les fonctions doivent respecter :

``` text
(year_suffix text,
 region text,
 ue text,
 cfg jsonb,
 form_id text)
```

------------------------------------------------------------------------

## 6️⃣ 🔐 Règles de filtrage obligatoires (STRICT)

**`user_ref1` est obligatoire en permanence** : il représente la coop
active et permet de filtrer toutes les données.

🔥 Précision contractuelle ajoutée :

-   `user_ref1` doit obligatoirement être injecté via
    `cfg_from_payload`.
-   Si absent dans `cfg`, la fonction doit lever une erreur.
-   Aucun fallback permis.
-   Aucun OR permissif autorisé.
-   Aucune requête cross-coop.

Toutes les fonctions SQL doivent filtrer STRICTEMENT par :

``` sql
WHERE t.unite_d_echantillonnage_ue = p_ue
  AND t.region = p_region
  AND t.user_ref1 = (p_cfg->>'user_ref1')
```

### Règle STRICT officielle

-   `user_ref1` est obligatoire.
-   Si `user_ref1` est NULL ou vide → la fonction doit lever une erreur.
-   Aucun OR permissif autorisé.
-   Aucune requête cross-coop.

⚠ Interdit :

-   `(cfg.user_ref1 IS NULL OR ...)`
-   Requêtes cross-coop
-   Absence de filtre `user_ref1`
-   Absence de filtre `region`
-   Absence de filtre `ue`

------------------------------------------------------------------------

## 7️⃣ 📦 Résolution dynamique des tables

Interdit (hardcodé) :

FROM "1052897"."1052897_coefficient_de_distribution1"

Obligatoire (dynamique) :

-   `schema = p_form_id`
-   `table  = p_form_id` (table parent)
-   Sous-tables = `p_form_id || '_suffix'`

Utiliser `format()` avec `%I` :

``` sql
v_sql := format(
  'SELECT ... FROM %I.%I t WHERE ...',
  p_form_id,
  p_form_id
);
```

🔹 Cas particulier : `Source = #"form_id"` (Power Query)

Quand une requête M contient :

`Source = #"1052897"`

Cela correspond en SQL à :

`FROM p_form_id.p_form_id`

Donc :

-   Le schéma est toujours `p_form_id`
-   La table parent est toujours `p_form_id`
-   Aucune table ne doit être hardcodée

------------------------------------------------------------------------

## 8️⃣ 📏 ORDER BY obligatoire

Le moteur Python ne garantit pas l'ordre.\
Le **SQL doit garantir** l'ordre final.

Exemples :

``` sql
ORDER BY "ID__PLACET" ASC, "NO_MICRO_P" ASC
```

ou

``` sql
ORDER BY parcelle_int ASC, no_micro_p ASC
```

------------------------------------------------------------------------

## 🔹 Override global `id_projet` (ID__PLACET) 🔥 (NOUVELLE SECTION)

🎯 Objectif

Permettre de remplacer dynamiquement le préfixe de `ID__PLACET`.

Par défaut :

`unite_d_echantillonnage_ue-00001`

Avec override :

`TESTPROJET-00001`

------------------------------------------------------------------------

### 🔧 Implémentation SQL obligatoire

``` sql
COALESCE(
  NULLIF(btrim(p_cfg->>'id_projet'), ''),
  src.unite_d_echantillonnage_ue
)
|| '-' || numero_parcelle_fmt
```

------------------------------------------------------------------------

### 📦 Règles obligatoires

-   `id_projet` doit être déclaré dans `cfg_from_payload`
-   Si absent → comportement normal
-   Si vide → comportement normal
-   Si présent → override complet du préfixe
-   Fonctionne dans toutes les tables DDIF

❌ Interdit

-   Lire directement `p_ue` pour construire ID__PLACET
-   Hardcoder unite_d_echantillonnage_ue sans COALESCE
-   Override partiel
-   Traitement spécial par export

------------------------------------------------------------------------

## 🔹 Padding standard DDIF (`nb_0`)

Le padding des parcelles est contrôlé exclusivement par `nb_0` (contenu
dans `cfg`).

``` sql
CASE
  WHEN (SELECT nb_0 FROM cfg) > 0 THEN
    lpad(
      right(
        regexp_replace(numero_de_parcelle::text, '\\D', '', 'g'),
        (SELECT nb_0 FROM cfg)
      ),
      (SELECT nb_0 FROM cfg),
      '0'
    )
  ELSE
    regexp_replace(numero_de_parcelle::text, '\\D', '', 'g')
END
```

------------------------------------------------------------------------

## 9️⃣ 📊 Écriture DBF FoxPro (sans Excel)

Le writer DBF suit exactement la philosophie : **copie exacte du template + écriture values-only dans la copie**, sans toucher au template original.

### 9.0 Technologies / fichiers impliqués

-   `dbf_writer.py` (writer DBF)
-   `build_ddif_exports.py` (orchestrateur : lit templates/config/sql, exécute SQL, écrit DBF, upload)

**Important :** on est sur des **`.DBF` FoxPro** (le *viewer* ou le logiciel avaleur peut être FoxPro/VFP, mais côté moteur on gère le fichier DBF au niveau binaire).

### 9.1 Règles strictes (writer)

-   Copier le template `.DBF` → output (copie exacte : metadata/fichiers identiques au maximum)
-   Lire la structure (fields) **depuis le DBF copié** (donc exactement le template)
-   Écrire uniquement les records (values-only) à partir de `header_len`
-   Ne jamais changer l'ordre des colonnes : l'ordre final est celui du template
-   Ne jamais “inventer” des champs : si un champ est dans le template, il doit être rempli (ou vide) selon les règles
-   Ne jamais dépendre d’Excel / COM / conversion

### 9.2 Détails techniques confirmés (d'après tes scripts)

Ces points sont **vérifiés** dans `dbf_writer.py` :

-   **EOF** : le writer écrit un marqueur EOF **`0x1A`** à la fin du fichier, puis fait `truncate()` pour enlever tout résidu après les données.
-   **Record count** : le writer patch le record count dans le header DBF **aux bytes 4..7** (uint32 little-endian) via un `struct.pack("<I", record_count)`.
-   **Date du header** : le writer met à jour la date du header DBF (année, mois, jour) quand `patch_date=True` (par défaut activé), en utilisant la date du jour.

### 9.3 Encodage / types DBF (règles)

Dans le writer :

-   Champs `C` (texte) : encodage **cp1252** avec `errors="replace"` (pour éviter de casser le fichier si caractères non supportés).
-   Champs `D` (date) : écriture `YYYYMMDD` (8 chars ASCII) si la valeur est un `date` / `datetime`.
-   Champs `N` / `F` (numérique) :
    -   aligné à droite, rempli d'espaces
    -   respect strict de `(length, decimals)` du template
    -   si `decimals=0`, on écrit un entier (pas de décimales)
-   Champs `L` (logical) : `T` / `F` / `?` (valeur inconnue)
-   Champs spéciaux (ex: `type_code '0'` qu'on voit dans certains DBF) : écrit en bytes little-endian sur la longueur du champ.

### 9.4 Position d'écriture (critique)

Le writer écrit **toujours** au début de la zone records :

-   `seek(header_len)`
-   écriture des records
-   écriture `0x1A`
-   `truncate()`

Ce comportement est volontaire pour éviter les DBF “patchés” où un EOF existant était déjà présent (et qui ferait écrire après, au mauvais endroit).

### 9.5 “Troncature” / compat avaleur (DBF)

La logique “pas de résidu après la fin des données” est assurée par :

-   écriture du marqueur EOF
-   `truncate()` juste après

Objectif : ne pas laisser d'ancien contenu (records/EOF) du template après les nouvelles données.

------------------------------------------------------------------------

## 🔟 🛡 Résilience

Règle d'or :

> Une feuille qui échoue ne doit jamais casser le run complet.

Implémentation :

-   Si SQL échoue → `rows = []`, log, on copie+upload le template vide
-   Si l'écriture DBF échoue → fallback copie brute + upload
-   Le pipeline continue toujours pour les autres exports

------------------------------------------------------------------------

## 1️⃣1️⃣ 📅 Reproductibilité historique

Une année est figée :

-   `ddif/2025-2026/`

On ne modifie jamais un pack livré.

Nouvelle année :

-   copie → `ddif/2026-2027/`
-   ajustements SQL/templates
-   tests
-   livraison

------------------------------------------------------------------------

## 1️⃣2️⃣ ❌ Ce que le système ne doit jamais faire

-   Logique métier en Python
-   Code spécifique région
-   `form_id` hardcodé
-   Excel COM
-   Conversion XLSX
-   Modification de formats
-   Déduire les colonnes finales depuis SQL (le template est la source
    de vérité)

------------------------------------------------------------------------

## 1️⃣3️⃣ ✅ Checklist --- Ajouter une nouvelle feuille (nouvel export)

### A) Ce que tu fournis quand tu demandes de l'aide

-   Le nom de l'export (ex: `DNBR_DEG`, `DEF_ESP`, etc.)
-   La requête Power Query **(M)** complète
-   La liste finale des colonnes (ordre exact)
-   Les paramètres runtime nécessaires (`nb_0`, `user_ref1`, `mtm`,
    `id_projet`, etc.)
-   Les règles particulières imposées par l'année/région

⚠ Pas nécessaire :

-   Mapping Excel (déjà programmé dans le writer)
-   A1/A2
-   Sentinel
-   `form_id`

### B) Ce que la solution doit livrer

1)  **Créer `sql/<EXPORT>.sql`**
    -   `CREATE OR REPLACE FUNCTION app.ddif_<year_suffix>_<traitement>_<region>_<export>`
    -   Résolution dynamique des tables via `p_form_id`
    -   Filtres STRICT : `user_ref1`, `region`, `ue`
    -   `ORDER BY` cohérent
    -   Retourne EXACTEMENT les colonnes finales (ordre exact)
2)  **Ajouter l'entrée dans `config.yaml`**
    -   `install_file: "sql/<EXPORT>.sql"`
    -   `function: "app.ddif_<year_suffix>_<traitement>_<region>_<export>"`
    -   `cfg_defaults` au besoin
    -   `cfg_from_payload` pour les paramètres requis (**toujours
        inclure `user_ref1` et `id_projet` si supporté**)
3)  **Tester**
    -   `python build_ddif_exports.py --payload-file test_payload.json`
    -   Vérifier log `rows=...`
    -   Vérifier fichier `.DBF` final (ouverture dans ton outil avaleur)

------------------------------------------------------------------------

## 1️⃣4️⃣ 🧠 Méthode --- Transformer une requête Power Query (M) → SQL DDIF

Quand tu me donnes une requête M, l'objectif est de produire
**l'équivalent SQL** dans la fonction du pack.

### A) Pattern de conversion (guide rapide)

-   `Source = Odbc.Query(...)` → devient `FROM %I.%I` (dynamique avec
    `p_form_id`)
-   `Table.SelectRows` → devient `WHERE ...`
-   `Table.AddColumn` → devient `SELECT ..., <expression> AS <col>`
-   `Text.PadStart / Text.End / Text.From` → devient
    `lpad / right / ::text`
-   concaténation → `||`
-   `if ... then ... else` → `CASE WHEN ... THEN ... ELSE ... END`
-   `Table.Group` → `GROUP BY`
-   `Table.Sort` → `ORDER BY`
-   `Table.Join` → `JOIN` (souvent `LEFT JOIN`)
-   nettoyage "numérique" → `regexp_replace(..., '\\D', '', 'g')`

### B) Sortie attendue

Un SQL "final values" : les colonnes retournées sont déjà prêtes à être
écrites dans le `.DBF` (et doivent matcher le template).

### C) Pièges classiques

-   Ne pas hardcoder `form_id`
-   Toujours utiliser la résolution dynamique
-   Toujours inclure `ORDER BY`
-   Toujours appliquer le filtrage STRICT

------------------------------------------------------------------------

## 1️⃣5️⃣ 🧭 Résumé fondamental (MIS À JOUR)

Le template décide des colonnes.\
Le SQL décide des valeurs.\
Le pack décide des règles.\
`user_ref1` décide de la coop.\
`nb_0` décide du padding.\
`id_projet` peut override le préfixe ID__PLACET.\
`form_id` est toujours dynamique.\
Python transporte uniquement les données.
