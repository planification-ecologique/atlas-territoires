"""Jeu de données de démonstration, SYNTHÉTIQUE.

Il sert à faire tourner l'application sans télécharger les sources (plusieurs
Go). Les motifs imitent grossièrement la géographie du Centre-Val de Loire
(villes, Loire, Sologne, Beauce...) mais AUCUNE valeur n'est réelle.
L'application affiche un bandeau "données de démonstration" quand
`manifest.synthetic` est vrai.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from shapely.geometry import LineString, Point, Polygon

from . import grid
from .export import write_region, write_registry
from .registry import Registry

# Contour approximatif de la région (lng, lat), tracé à la main.
CVL_OUTLINE = [
    (1.45, 48.94), (1.80, 48.70), (2.00, 48.30), (2.45, 48.13), (2.95, 48.15),
    (3.10, 47.80), (2.88, 47.55), (3.07, 47.10), (2.95, 46.80), (2.60, 46.42),
    (2.20, 46.42), (1.75, 46.45), (1.40, 46.36), (1.00, 46.55), (0.85, 46.75),
    (0.60, 46.95), (0.25, 47.00), (0.06, 47.25), (0.20, 47.55), (0.60, 47.70),
    (0.80, 48.05), (0.85, 48.35), (0.80, 48.67),
]

CITIES = [  # nom, lng, lat, poids
    ("Tours", 0.69, 47.39, 300), ("Orléans", 1.91, 47.90, 290), ("Bourges", 2.40, 47.08, 100),
    ("Chartres", 1.49, 48.45, 90), ("Châteauroux", 1.69, 46.81, 70), ("Blois", 1.33, 47.59, 65),
    ("Dreux", 1.37, 48.74, 45), ("Montargis", 2.73, 48.00, 40), ("Vierzon", 2.07, 47.22, 30),
    ("Vendôme", 1.07, 47.79, 17), ("Romorantin-Lanthenay", 1.74, 47.36, 17), ("Gien", 2.63, 47.69, 14),
    ("Amboise", 0.98, 47.41, 13), ("Issoudun", 1.99, 46.95, 12), ("Chinon", 0.24, 47.17, 8),
]

RIVERS = {  # (ligne, largeur de la zone inondable en km)
    "Loire": ([(3.07, 47.00), (2.92, 47.33), (2.74, 47.64), (2.63, 47.69), (2.37, 47.77),
               (1.91, 47.90), (1.63, 47.78), (1.33, 47.59), (0.98, 47.41), (0.69, 47.39),
               (0.41, 47.33), (0.07, 47.21)], 3.0),
    "Cher": ([(2.40, 46.75), (2.07, 47.22), (1.55, 47.27), (1.18, 47.34), (0.69, 47.37)], 1.6),
    "Indre": ([(1.69, 46.81), (1.25, 47.05), (1.00, 47.13), (0.30, 47.25)], 1.2),
    "Loir": ([(1.30, 48.20), (1.07, 47.79), (0.60, 47.70)], 1.0),
}

NATURA = [(1.90, 47.50, 35), (1.25, 46.72, 20), (2.10, 47.98, 12), (0.45, 47.55, 8), (2.80, 47.25, 8)]
ZNIEFF = [(1.25, 46.72, 14), (2.10, 47.98, 9), (1.70, 47.45, 10), (0.85, 47.15, 6), (2.55, 46.65, 7), (1.30, 48.60, 5)]
FARMLAND = [(1.70, 48.15, 55, 0.9), (2.10, 46.98, 35, 0.85), (2.60, 47.30, 25, 0.6), (0.70, 47.95, 25, 0.6)]
WIND = [(1.75, 48.25, 35), (2.15, 46.95, 25), (1.40, 48.05, 20)]


def _km(a: np.ndarray, lng: float, lat: float) -> np.ndarray:
    dx = (a[:, 0] - lng) * 111.32 * np.cos(np.radians(47.5))
    dy = (a[:, 1] - lat) * 110.57
    return np.hypot(dx, dy)


def _noise(rng: np.random.Generator, centers: np.ndarray, n_bumps: int = 400, scale_km: float = 8) -> np.ndarray:
    """Bruit spatial lisse dans [0, 1] (somme de bosses gaussiennes)."""
    lo, hi = centers.min(0), centers.max(0)
    pts = rng.uniform(lo, hi, size=(n_bumps, 2))
    acc = np.zeros(len(centers))
    for x, y in pts:
        acc += rng.normal() * np.exp(-((_km(centers, x, y) / scale_km) ** 2))
    acc -= acc.min()
    return acc / (acc.max() or 1)


def _river_dist(centers: np.ndarray, line: list[tuple[float, float]]) -> np.ndarray:
    # Distance approximative en km, en projetant grossièrement en plan local.
    k = np.array([111.32 * np.cos(np.radians(47.5)), 110.57])
    ls = LineString([(x * k[0], y * k[1]) for x, y in line])
    return np.array([ls.distance(Point(x * k[0], y * k[1])) for x, y in centers])


def build_demo(reg: Registry, out: Path, region: str = "24", res: int = 8, seed: int = 24) -> dict:
    rng = np.random.default_rng(seed)
    cells = grid.cells_for_polygon(Polygon(CVL_OUTLINE), res)
    areas = grid.cell_areas_km2(cells)
    c = grid.cell_centers(cells)
    n = len(cells)

    # Population : agglomérations + semis rural.
    urban = np.zeros(n)
    for _, x, y, w in CITIES:
        r = 1.5 + 0.9 * np.sqrt(w / 10)
        urban += w * 1200 / (np.pi * r**2) * np.exp(-((_km(c, x, y) / r) ** 2))
    rural = 6 + 45 * _noise(rng, c, 300, 6) ** 2
    density = urban + rural * (rng.random(n) < 0.85)
    residents = density * areas

    city_core = np.zeros(n)
    for _, x, y, w in CITIES:
        city_core = np.maximum(city_core, np.exp(-((_km(c, x, y) / (1.5 + np.sqrt(w) / 5)) ** 2)))

    south = np.clip((47.8 - c[:, 1]) / 1.4, 0, 1)
    age65 = 0.18 + 0.12 * south + 0.06 * _noise(rng, c, 200, 10) - 0.06 * city_core
    poverty = 0.07 + 0.14 * city_core + 0.06 * south * _noise(rng, c, 200, 12)
    age65[residents < 20] = np.nan
    poverty[residents < 30] = np.nan

    # Inondation : bandes le long des cours d'eau.
    flood = np.zeros(n)
    for line, width in RIVERS.values():
        d = _river_dist(c, line)
        flood = np.maximum(flood, np.clip(1.15 - d / width, 0, 1))
    flood = np.clip(flood * (0.8 + 0.4 * rng.random(n)), 0, 1)

    def blobs(spec, sharp=2.0):
        v = np.zeros(n)
        for x, y, r in spec:
            v = np.maximum(v, np.exp(-((_km(c, x, y) / r) ** sharp)))
        return v

    noise_n = _noise(rng, c, 250, 4)
    natura = np.clip(blobs(NATURA, 3) * 1.2 - 0.25 + 0.3 * (noise_n - 0.5), 0, 1)
    natura = np.maximum(natura, (flood > 0.6) * 0.8 * (c[:, 1] > 47.2))  # vallée de la Loire
    natura[natura < 0.05] = 0
    znieff = np.clip(blobs(ZNIEFF, 3) * 1.3 - 0.35 + 0.4 * (_noise(rng, c, 250, 3) - 0.5), 0, 1)
    znieff[znieff < 0.05] = 0

    farm = np.full(n, 0.35)
    for x, y, r, lvl in FARMLAND:
        farm = np.maximum(farm, lvl * np.exp(-((_km(c, x, y) / r) ** 2)))
    farm = np.clip(farm * (1 - 0.8 * natura) * (1 - city_core) + 0.15 * (_noise(rng, c, 300, 5) - 0.5), 0, 1)

    # Consommation d'espaces : couronnes périurbaines et axes.
    periurban = np.zeros(n)
    for _, x, y, w in CITIES:
        d = _km(c, x, y)
        r = 3 + 2 * np.sqrt(w / 10)
        periurban += np.sqrt(w) * np.exp(-(((d - r) / (r * 0.9)) ** 2))
    conso = 0.15 * periurban * (0.4 + _noise(rng, c, 400, 3)) + 0.6 * (rng.random(n) < 0.08) * rng.random(n)
    conso[rng.random(n) < 0.35] = 0
    conso_hab = np.clip(0.72 - 0.35 * city_core + 0.35 * (_noise(rng, c, 200, 6) - 0.5), 0, 1)
    conso_hab[conso < 0.05] = np.nan

    wind = blobs(WIND, 2)
    enr = np.where(rng.random(n) < 0.12 * (0.3 + wind), rng.gamma(1.5, 1.2, n) * (0.5 + 2 * wind), 0.0)
    enr += np.where(rng.random(n) < 0.03, rng.gamma(1.2, 0.8, n), 0)  # solaire au sol épars

    # Hydraulique : quelques centrales le long des cours d'eau (zones inondables).
    hydro = np.where((flood > 0.3) & (rng.random(n) < 0.03), rng.gamma(1.0, 1.5, n), 0.0)

    values = {
        "pop_densite": density,
        "pop_habitants": residents,
        "pop_65plus_part": age65,
        "pauvrete_part": poverty,
        "conso_enaf": conso,
        "conso_habitat_part": conso_hab,
        "inondation_eaip": flood,
        "natura2000": natura,
        "znieff1": znieff,
        "agri_part": farm,
        "enr_puissance": enr,
        "hydro_puissance": hydro,
    }
    values = {k: np.asarray(v, dtype=np.float32) for k, v in values.items()}
    write_registry(reg, out)
    places = [{"name": name, "lng": x, "lat": y} for name, x, y, _ in CITIES]
    return write_region(reg, out, region, res, cells, areas, values, synthetic=True, places=places)
