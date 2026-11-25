# Feuille de route

## Fait (prototype)

- Registre des indicateurs et des paires en YAML, validé par `python -m atlas_pipeline check`.
- Pipeline H3 r8 pour une région, avec quatre familles de méthodes d'agrégation et des tests.
- Application statique en français : paires classées, composition libre, indicateurs, infobulles, recherche.
- Jeu de démonstration synthétique pour le Centre-Val de Loire.

## Prochaines étapes

1. **Premier passage sur les vraies données** du Centre-Val de Loire : confirmer les URL et les noms de
   colonnes marqués `verify: true` dans `pipeline/sources.yaml`, remplacer le jeu synthétique.
2. **Relire les seuils** "élevé" et "faible" avec des experts métier (DGALN, Cerema, DREAL) : ce sont eux qui
   déterminent les surfaces affichées.
3. **Couches propres à la France** qui font la valeur ajoutée : zonage des PLU (zones AU), friches
   (Cartofriches), retrait-gonflement des argiles, recul du trait de côte, zones d'accélération des EnR,
   projections TRACC (DRIAS), tension sur la ressource en eau.
4. **Agrégation par territoire** : EPCI, SCoT (pour le ZAN), départements, avec un tableau des paires par
   territoire.
5. **Passage à l'échelle nationale** : rendu WebGL H3, r9 chargé par fenêtre, index commune en int32 (déjà
   en place).
6. **Hébergement et gouvernance** : où l'outil est publié, qui maintient les données et à quel rythme.
7. **Contact avec l'auteur de land.toekom.st** (Ganesh Babu) pour comparer les méthodes de seuils et
   d'explication des indicateurs.
