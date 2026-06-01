# Brouillon — Catalogue de champs UE (`field_definitions`)

Source de vérité des champs : `app.prescriptions` (schéma existant, **non modifié**).
Convention reprise du DATA_MANUELLE : 🟧 requis · 🟨 requis conditionnel · ⬜ dérivé · ⚪ optionnel.
Source : **auto** = rempli par le DBF · **manuel** = saisie web · **dérivé** = calculé.

> ⚠️ À VALIDER : la colonne `source` (auto/manuel) et le statut requis sont mes meilleures
> hypothèses. Les types viennent directement de `app.prescriptions`.

## 🟧 Requis (toujours)

| Champ | Type | Source | Notes |
|---|---|---|---|
| `unite_d_echantillonnage_ue` | texte | auto (DBF) | clé métier |
| `region` | liste | manuel | BSL, GIM, SLSJ, CN, ABIT… (= sélecteur) |
| `rayon` | numerique | manuel | ex. 1.26 |
| `gradient_intensite` | liste | manuel | Intensif, De base |
| `code_dica` | liste | manuel | depuis `dica_codes` (= déclenche le traitement) |

## ⬜ Dérivé (calculé, non saisi)

| Champ | Type | Source | Dérivé de |
|---|---|---|---|
| `traitement` | texte | dérivé | `code_dica` → `dica_codes.traitement` |

## 🟨 Requis conditionnel (selon traitement / région)

| Champ | Type | Devient requis quand |
|---|---|---|
| `plant_ha` | numerique | `traitement` ∈ {REB, REG} |
| `traitement_ps` | texte | `traitement` ∈ {DEBL, SCA} (aussi pré-rempli via `dica_codes`) |
| `denombrement_cn` | entier | `region` = CN ET `traitement` contient "AVT" |
| `taux_occ_andain` | numerique | `region` = ABIT ET `traitement` ∈ {DEG, NET, EPC} |

## 🟦 Auto (du DBF) — optionnels sauf indication

| Champ | Type | Source |
|---|---|---|
| `no_prescription` | texte | auto |
| `secteur_intervention` | texte | auto |
| `chantier` | texte | auto |
| `uaf` | texte | auto |
| `code_ratf` | texte | auto |
| `contrat` | texte | auto |
| `projet` | texte | auto |
| `ha_prescription` | numerique | auto (somme des blocs) |
| `entrepreneur_travaux` | texte | auto |
| `debut` | date | auto |
| `fin` | date | auto |

## ⚪ Optionnels manuels (de `app.prescriptions`)

| Champ | Type |
|---|---|
| `nb_parcelle_ue` | entier |
| `parcelle_faite` | texte (booléen ?) |
| `directive_op` | texte |
| `ha_net` | numerique |
| `origine` | texte |
| `preparation_de_terrain` | texte |
| `type_de_degagement` | texte |
| `equip_utilise` | texte |
| `methode_andains` | texte |
| `nb_si_reboisement` | numerique |
| `plant_max` | numerique |
| `plant_reboise` | numerique |
| `ms_propice` | numerique |
| `note_1` | texte |
| `andain` | numerique |
| `entre_andain` | numerique |
| `stocking_av_tr` | numerique |

## Points à confirmer

1. **`appweb.ue` doit être aligné sur `app.prescriptions`** : ma table `ue` n'a qu'un sous-ensemble. Pour « garder toute l'info au niveau UE », il faut ajouter les ~22 colonnes manquantes (code_dica, nb_parcelle_ue, traitement_ps, denombrement_cn, taux_occ_andain, directive_op, ha_net, origine, preparation_de_terrain, type_de_degagement, equip_utilise, methode_andains, nb_si_reboisement, plant_max, plant_reboise, ms_propice, note_1, andain, entre_andain, parcelle_faite). → OK pour aligner ?
2. **`PLT_ADMIS` (DBF) → `plant_ha` ou `plant_max` ?** Les deux existent. `plant_ha` est jaune conditionnel (manuel). Donc PLT_ADMIS = `plant_max` ?
3. **Source auto/manuel** : confirme ma colonne (surtout les cas mixtes).
4. **`dica_codes`** : déposer le CSV pour seed propre (~150 codes).
