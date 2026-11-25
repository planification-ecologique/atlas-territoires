# Format des fichiers de données

L'application ne lit que des fichiers statiques produits par le pipeline. Tous les tableaux binaires d'une
région et d'une résolution sont **alignés** : l'élément `i` de chaque fichier décrit la même cellule H3.

```
data/
  registry.json                 thèmes, indicateurs (sans les paramètres de calcul), paires, régions
  <région>/
    manifest.json               nombre de cellules, surface, seuils de classes, statistiques, paires, lieux
    communes.json               codes et noms des communes (build réel seulement)
    r<res>/
      cells.u64                 cellules H3, uint64 little-endian, triées
      commune.i32               position de la commune de chaque cellule dans communes.json, -1 sinon
      <indicateur>.f32          valeurs float32 little-endian, NaN = pas de donnée
      <indicateur>.c8           classes uint8 : 0 = pas de donnée, 1 à 5 de la plus basse à la plus haute
```

## Tailles

Pour le Centre-Val de Loire en r8 (60 000 cellules) : 480 Ko pour `cells.u64`, 240 Ko par `.f32`, 60 Ko par
`.c8`, avant compression HTTP.

Pour la métropole entière, on attend environ 750 000 cellules en r8 (3 Mo par `.f32`). C'est encore
chargeable d'un bloc, mais le rendu GeoJSON de MapLibre ne suivra pas : il faudra passer à un rendu H3 en
WebGL (deck.gl `H3HexagonLayer`) ou à des tuiles vectorielles, et découper r9 par cellule parente r5.

## Différences avec land.toekom.st

- L'index cellule vers commune est en int32 (34 900 communes dépassent l'int16 utilisé aux Pays-Bas).
- Les valeurs et les classes sont dans deux fichiers séparés : on charge les classes pour l'affichage et les
  valeurs pour les seuils et les infobulles.
