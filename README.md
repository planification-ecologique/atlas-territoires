# Atlas des territoires

Prototype d'outil pour **croiser les enjeux d'aménagement sur une grille commune** et faire apparaître les
conflits et les synergies entre politiques publiques : sobriété foncière (ZAN), risques, biodiversité,
agriculture, énergies renouvelables, population.

Il est conçu pour aider à **se poser les bonnes questions** sur la Stratégie nationale d'aménagement du
territoire (SNAT) : chaque paire de conflit ou de synergie porte une question explicite, et la carte montre
où, et pour combien d'hectares et d'habitants, elle se pose.

L'approche reprend l'architecture de [land.toekom.st](https://land.toekom.st/) (Pays-Bas), reconstruite pour
la France sans réutiliser son code : application statique, grille hexagonale [H3](https://h3geo.org),
indicateurs pré-calculés en tableaux binaires, paires définies comme des données.

> **État : prototype.** Une région (Centre-Val de Loire), résolution H3 8 (hexagones d'environ 74 ha),
> 11 indicateurs, 13 paires. Le dépôt contient les données réelles construites par le pipeline à partir des
> sources ouvertes (voir plus bas).

## Ce que fait l'outil

- **Conflits et synergies** : liste des paires classées par surface concernée. Pour chaque paire : la question
  posée à la SNAT, les deux conditions, la carte du recouvrement, les hectares, les habitants concernés et la
  part de chaque condition prise dans le recouvrement.
- **Composer** : croiser librement deux indicateurs (élevé ou faible) pour tester une tension qui n'est pas
  encore dans la liste.
- **Indicateurs** : chaque couche en 5 classes, avec sa définition, sa source et sa licence ; survol d'un
  hexagone pour lire toutes les valeurs.

## Organisation du dépôt

```
registry/            le "contenu" de l'outil, en YAML
  indicators.yaml    indicateurs : thème, rôle, unité, méthode, source, seuils haut/bas
  pairs.yaml         paires conflit/synergie et la question SNAT de chacune
  regions.yaml       régions disponibles
pipeline/            Python : sources ouvertes -> grille H3 -> fichiers binaires
  sources.yaml       URL, licences et colonnes des sources brutes
  atlas_pipeline/    méthodes d'agrégation, classement, export, jeu de démo
web/                 application React + MapLibre + h3-js, sans serveur
  public/data/       fichiers produits par le pipeline (versionnés)
docs/                format des données, feuille de route
```

Ajouter une paire ne demande qu'une entrée dans `registry/pairs.yaml`. Ajouter un indicateur demande une
entrée dans `registry/indicators.yaml`, une source dans `pipeline/sources.yaml` et, si aucune méthode
existante ne convient, une fonction dans `pipeline/atlas_pipeline/indicators.py`.

## Démarrer

Application (avec les données déjà présentes) :

```bash
cd web
npm install
npm run dev        # http://localhost:5173
```

Pipeline :

```bash
cd pipeline
pip install -e ".[dev]"
python -m atlas_pipeline check     # valide le registre
python -m atlas_pipeline demo      # régénère le jeu synthétique
python -m atlas_pipeline build     # construit depuis les sources ouvertes (plusieurs Go)
python -m atlas_pipeline report    # résume les paires de la région construite
pytest
```

`build` télécharge les sources dans `pipeline/cache/raw/` (environ 1,2 Go, 3 Go une fois décompressées ; 7z est
nécessaire). L'EAIP est lue objet par objet sur le WFS Géorisques, lent (compter une demi-heure). Une source sans URL peut être déposée à la main dans `pipeline/cache/raw/<id>/`. `demo` écrase les données versionnées :
utiliser `--out` pour l'écrire ailleurs. Un indicateur dont la source manque est ignoré, et l'application n'affiche que ce qui a été construit.

## Déploiement

Chaque push sur `main` déploie l'application sur GitHub Pages, une fois les tests passés (job `deploy` de
`.github/workflows/ci.yml`, relançable à la main depuis l'onglet Actions). Prérequis, une seule fois :
Settings > Pages > Source = **GitHub Actions**.

## Méthodes d'agrégation

| Méthode | Usage | Exemple |
| --- | --- | --- |
| `grid_sum`, `grid_sum_density`, `grid_ratio` | carreaux fins (200 m) affectés à l'hexagone qui contient leur centre | Filosofi : habitants, densité, part des 65 ans et plus |
| `grid_areal_density`, `grid_areal_ratio` | grille plus grossière (1 km) répartie au prorata des surfaces | consommation d'espaces du Cerema |
| `polygon_share` | part de l'hexagone couverte par des zonages | Natura 2000, ZNIEFF, EAIP, RPG |
| `commune_spread_density` | valeur communale répartie sur les hexagones de la commune | registre des installations EnR |

Les classes sont soit des seuils fixés à la main (lisibles, comparables entre régions), soit des quantiles
(avec un traitement à part des valeurs nulles). Pour une paire, "élevé" et "faible" renvoient aux seuils
`high` et `low` de chaque indicateur.

## Sources

Toutes les sources du prototype sont ouvertes (Licence Ouverte 2.0) : Insee Filosofi 2021 carroyé à 200 m,
Cerema consommation d'espaces NAF 2011-2025, EAIP cours d'eau, INPN (Natura 2000, ZNIEFF), IGN (ADMIN EXPRESS,
RPG, fond Plan IGN), ODRÉ registre national des installations de production d'électricité. Le détail, les
URL et les millésimes sont dans [`pipeline/sources.yaml`](pipeline/sources.yaml), vérifiés en novembre 2026.

## Suite

Voir [`docs/feuille-de-route.md`](docs/feuille-de-route.md).
