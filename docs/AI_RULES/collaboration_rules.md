# Règles de collaboration

## Proposer avant de modifier

Pour tout changement sur un fichier existant :
1. Expliquer ce qui va changer et **pourquoi**
2. Attendre la validation explicite avant d'écrire quoi que ce soit

Ne jamais modifier un fichier en supposant que c'est évident ou que le contexte suffit.

---

## Expliquer le pourquoi

Pas juste "je vais changer X" — mais "je propose de changer X parce que Y".

Si la raison n'est pas claire, poser la question plutôt que de deviner.

---

## Présenter des options quand il y a un choix

Si plusieurs approches sont valides, les présenter avec les avantages et inconvénients de chacune, puis laisser le choix. Ne pas décider seul.

---

## Ne pas élargir le scope

Si on travaille sur A, ne pas toucher à B "tant qu'on y est". Demander d'abord.

Ne jamais modifier un fichier `.py` sans demande explicite.

---

## Poser la question si c'est ambigu

Ne jamais deviner l'intention. Ne jamais remplir les blancs tout seul. Si la demande est ambiguë, poser une question courte avant de commencer.

---

## Impacts à vérifier après chaque changement

| Action | À vérifier / mettre à jour |
|---|---|
| Nouveau script dispatcher | Nouveau modèle Pydantic dans `payload_models.py` + `docs/scripts_overview.md` + `docs/payloads_by_script.md` |
| Touche la BD | Vérifier si `safe_db.py` a déjà le helper avant d'en créer un nouveau |
| Nouveau helper dans `safe_db.py` | `docs/scripts_overview.md` section safe_db |
| Modifie un modèle Pydantic | Vérifier que le script correspondant l'importe correctement |
| Changement de payload d'un script | `payload_models.py` + `docs/payloads_by_script.md` |
| Modification du comportement d'un script | Commentaires du script mis à jour + `docs/scripts_overview.md` si le rôle change |
| Nouvelle coop | `docs/ajout_nouvelle_coop.md` |
| Nouveau formulaire Kizeo | `docs/ajout_nouveau_formulaire_kizeo.md` |

---

## Voir aussi

- Règles techniques de patching du code : `docs/AI_RULES/patching_rules.md`
- Description de tous les scripts et leur rôle : `docs/scripts_overview.md`
