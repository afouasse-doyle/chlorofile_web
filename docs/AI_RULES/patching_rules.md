# Patching Rules

## Objectif

Modifier le minimum possible.

Le projet contient beaucoup de scripts de production qui fonctionnent.
Les patchs doivent être ultra conservateurs.

---

## Interdictions absolues

- Ne jamais supprimer des commentaires existants sans raison — si le comportement qu'ils décrivent change, mettre le commentaire à jour plutôt que de le laisser faux ou de le supprimer
- Ne jamais réécrire un fichier complet si ce n'est pas demandé
- Ne jamais reformater tout un fichier
- Ne jamais renommer des variables sans demande explicite
- Ne jamais déplacer des blocs inutilement
- Ne jamais changer les logs existants sans raison
- Ne jamais modifier l'architecture globale implicitement
- Ne jamais référencer ou s'inspirer du code dans `scripts/expires/` — code mort

---

## Règles

- Modifier uniquement ce qui est demandé
- Préserver la structure existante du fichier
- Respecter le style actuel (indentation, spacing, nommage)
- Conserver tous les commentaires existants
- Éviter les imports inutiles
- Préserver la compatibilité Flask dispatcher (`handle(payload, logger) -> dict`)
- Préserver la compatibilité `payload_models.py`
- Préserver la compatibilité `safe_db.py`

---

## Format d'un patch

Pour tout patch sur un script existant :

- Retourner le **fichier complet** (unité de déploiement)
- Inclure **tous les commentaires existants** sans exception
- N'apporter que les modifications demandées — **diff minimal**
- Aucune modification silencieuse (pas de nettoyage opportuniste, pas de reformatage en passant)

Quand on ajoute du code :
- Ajouter sans toucher aux blocs existants
- Respecter le style, l'indentation et les commentaires du fichier
- Garder la même logique globale

---

## Refactors

Ne jamais faire de refactor global non demandé explicitement.

Un bug fix ne justifie pas de nettoyer le code environnant.
Une nouvelle feature ne justifie pas de réorganiser les imports ou les fonctions existantes.

---

## Voir aussi

- Workflow de collaboration, proposer avant de modifier : `docs/AI_RULES/collaboration_rules.md`
