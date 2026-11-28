# Format des fichiers de données

L'application ne lit que des fichiers statiques produits par le pipeline. Tous les tableaux d'une
région et d'une résolution sont **alignés** : l'élément `i` de chaque fichier décrit la même cellule H3.

```
data/
  registry.json                 thèmes, indicateurs (sans les paramètres de calcul), paires, régions
  <région>/
    manifest.json               nombre de cellules, surface, seuils de classes, statistiques, paires, lieux
    communes.json               codes et noms des communes (build réel seulement)
    r<res>/
      cells.json                cellules H3, uint64 little-endian, triées
      commune.json              position de la commune de chaque cellule dans communes.json (int32), -1 sinon
      <indicateur>.json         { values : float32, NaN = pas de donnée ;
                                  classes : uint8, 0 = pas de donnée, 1 à 5 de la plus basse à la plus haute }
```

Chaque tableau est un objet `{"dtype": "<u8" | "<f4" | "<i4" | "u1", "length": n, "base64": "..."}` : les
octets little-endian du tableau, encodés en base64. On sert du JSON plutôt que des fichiers binaires bruts
(`.u64`, `.f32`) parce que les proxys des postes de l'administration (SPM) bloquent ces derniers (HTTP 403).
Le surcoût de 33 % du base64 est largement repris par la compression gzip de GitHub Pages.

## Tailles

Pour le Centre-Val de Loire en r8 (60 000 cellules) : 640 Ko pour `cells.json`, 400 Ko par indicateur,
avant compression HTTP.

Pour la métropole entière, on attend environ 750 000 cellules en r8 (3 Mo par `.f32`). C'est encore
chargeable d'un bloc, mais le rendu GeoJSON de MapLibre ne suivra pas : il faudra passer à un rendu H3 en
WebGL (deck.gl `H3HexagonLayer`) ou à des tuiles vectorielles, et découper r9 par cellule parente r5.

## Différences avec land.toekom.st

- L'index cellule vers commune est en int32 (34 900 communes dépassent l'int16 utilisé aux Pays-Bas).
- Les valeurs et les classes sont dans deux fichiers séparés : on charge les classes pour l'affichage et les
  valeurs pour les seuils et les infobulles.
