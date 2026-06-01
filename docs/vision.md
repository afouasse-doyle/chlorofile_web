# Vision du système — Chlorofile 2.0

Ce document décrit la direction stratégique du projet. Il doit être lu avant de proposer des changements sur les pipelines concernés.

---

## Ce qu'on remplace

### Pipeline data manuelle et listes Kizeo

Scripts actuellement en production mais en sursis :
- `create_kizeo_lists_excel.py`
- `create_kizeo_lists_json.py`
- `upload_lists_to_kizeo.py`
- `upsert_data_manuelle_db.py`

**Problème fondamental :** ces scripts s'appuient sur des fichiers Excel (`.xlsx`, `.xlsm`) comme source de vérité pour les données des coops (UE, prescriptions, listes Kizeo, etc.). Excel n'est pas une source de vérité fiable :
- Erreurs de saisie silencieuses
- Pas de validation à l'entrée
- Pas de traçabilité
- Fragilité du format (colonnes déplacées, feuilles mal nommées, etc.)

---

## Cible court terme — Application de saisie par coop

Remplacer le pipeline Excel par une **application de saisie** (web ou GUI desktop) que les coops utilisent directement pour entrer leurs données.

Fonctionnalités cibles :
- Saisie des UE, prescriptions, listes, etc. dans une interface structurée
- Validation des données à l'entrée (pas après coup dans Python)
- Synchronisation automatique vers **PostgreSQL** (source de vérité)
- Synchronisation automatique vers **Kizeo** (listes externes)

Contraintes :
- Interface simple — la lisibilité est plus importante que l'esthétique
- Sécurisée — accès par coop, données isolées par `user_ref1`
- Facile à maintenir — peu de dépendances, code simple

---

## Cible moyen terme — Interface IA en langage naturel

Sur la même plateforme (web), offrir aux utilisateurs la possibilité d'**interroger leurs données en langage naturel** via une IA.

Exemples de cas d'usage :
- "Montre-moi les UE de la coop X pour 2025-2026"
- "Combien de parcelles ont été traitées ce mois-ci ?"
- "Quels formulaires ont été remplis cette semaine ?"

Contraintes :
- Accès restreint aux données de la coop de l'utilisateur (RLS respectée)
- Simple à coder — pas besoin d'une interface sophistiquée
- Sécurisée — aucune donnée cross-coop, aucun accès en écriture non contrôlé

---

## Implications pour le développement aujourd'hui

### Ne pas investir dans le pipeline Excel

Les scripts listés ci-dessus sont en sursis. Ne pas :
- Ajouter de nouvelles fonctionnalités à ces scripts
- Les complexifier
- En créer de nouveaux dans la même veine (nouveaux parseurs Excel, nouvelles feuilles, etc.)

Si un bug bloquant est identifié : corriger le minimum. Pas de refactor, pas d'amélioration.

### Garder le schéma PostgreSQL propre et interrogeable

L'interface IA future va interroger directement la BD. Cela implique :
- Noms de tables et colonnes clairs et stables
- Données bien normalisées (pas de valeurs ambiguës, pas de colonnes fourre-tout)
- RLS active et correctement configurée sur toutes les tables exposées

### Ce qu'on continue à construire normalement

- Pipeline ingestion Kizeo → Flask → PostgreSQL
- Exports Excel/PDF via Kizeo
- DDIF
- Synchronisation catalogue Kizeo
- Rapport d'exécution

---

## Ce qui reste stable

Le cœur du système ne change pas :

```
Kizeo → Make → Flask → Scripts Python → PostgreSQL → SharePoint / ODBC
```

Seule la couche de **saisie manuelle** (Excel → scripts → BD) est remplacée par une interface directe.
