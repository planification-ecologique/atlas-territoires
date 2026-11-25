"""Grille H3 d'une région."""

from __future__ import annotations

import geopandas as gpd
import h3
import numpy as np
from shapely.geometry import Polygon, mapping

# Lambert-93, pour les calculs de surface.
L93 = "EPSG:2154"
WGS84 = "EPSG:4326"


def cells_for_polygon(geom, res: int) -> np.ndarray:
    """Cellules H3 dont le centre est dans la géométrie (WGS84), triées."""
    shape = h3.geo_to_h3shape(mapping(geom))
    cells = h3.h3shape_to_cells(shape, res)
    ints = np.array(sorted(h3.str_to_int(c) for c in cells), dtype=np.uint64)
    return ints


def cell_polygons(cells: np.ndarray) -> gpd.GeoDataFrame:
    """GeoDataFrame des hexagones (WGS84), index = position dans `cells`."""
    geoms = []
    for c in cells:
        ring = h3.cell_to_boundary(h3.int_to_str(int(c)))  # (lat, lng)
        geoms.append(Polygon([(lng, lat) for lat, lng in ring]))
    return gpd.GeoDataFrame({"cell": cells}, geometry=geoms, crs=WGS84)


def cell_areas_km2(cells: np.ndarray) -> np.ndarray:
    return np.array([h3.cell_area(h3.int_to_str(int(c)), "km^2") for c in cells], dtype=np.float64)


def cell_centers(cells: np.ndarray) -> np.ndarray:
    """Tableau (n, 2) lng, lat."""
    out = np.empty((len(cells), 2))
    for i, c in enumerate(cells):
        lat, lng = h3.cell_to_latlng(h3.int_to_str(int(c)))
        out[i] = (lng, lat)
    return out


def lookup(cells: np.ndarray, targets: np.ndarray) -> np.ndarray:
    """Position de chaque cellule cible dans `cells` (trié), -1 si absente."""
    idx = np.searchsorted(cells, targets)
    idx = np.clip(idx, 0, len(cells) - 1)
    found = cells[idx] == targets
    return np.where(found, idx, -1)


def points_to_cells(lng: np.ndarray, lat: np.ndarray, res: int) -> np.ndarray:
    return np.array(
        [h3.str_to_int(h3.latlng_to_cell(float(y), float(x), res)) for x, y in zip(lng, lat)],
        dtype=np.uint64,
    )
