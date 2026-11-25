"""Méthodes de calcul des indicateurs sur la grille H3.

Chaque méthode reçoit le contexte de la grille et une source déjà lue, et
renvoie un tableau float32 aligné sur `ctx.cells` (NaN = pas de donnée).
Le nom de la méthode est celui du champ `method` du registre.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from . import grid


@dataclass
class GridContext:
    res: int
    cells: np.ndarray          # uint64 trié
    areas_km2: np.ndarray      # float64
    polygons: gpd.GeoDataFrame  # WGS84, index = position
    communes: gpd.GeoDataFrame | None = None  # colonnes code, nom, geometry
    cell_commune: np.ndarray | None = None    # int32, position dans communes, -1 sinon

    @property
    def n(self) -> int:
        return len(self.cells)


METHODS: dict[str, Callable[..., np.ndarray]] = {}


def method(name: str):
    def deco(fn):
        METHODS[name] = fn
        return fn
    return deco


def _col(df: pd.DataFrame, name: str) -> pd.Series:
    lower = {c.lower(): c for c in df.columns}
    if name.lower() not in lower:
        raise KeyError(f"colonne '{name}' absente (colonnes : {list(df.columns)[:20]}...)")
    return pd.to_numeric(df[lower[name.lower()]], errors="coerce").fillna(0.0)


def _sum_by_cell(ctx: GridContext, gdf: gpd.GeoDataFrame, values: dict[str, pd.Series]) -> dict[str, np.ndarray]:
    """Somme de colonnes de carreaux fins (200 m) par hexagone, via leur centroïde."""
    pts = gdf.geometry.to_crs(grid.L93).centroid.to_crs(grid.WGS84)
    h = grid.points_to_cells(pts.x.values, pts.y.values, ctx.res)
    pos = grid.lookup(ctx.cells, h)
    keep = pos >= 0
    out = {}
    for k, s in values.items():
        acc = np.zeros(ctx.n)
        np.add.at(acc, pos[keep], s.values[keep])
        out[k] = acc
    return out


@method("grid_sum")
def grid_sum(ctx: GridContext, gdf: gpd.GeoDataFrame, field: str) -> np.ndarray:
    return _sum_by_cell(ctx, gdf, {"v": _col(gdf, field)})["v"].astype(np.float32)


@method("grid_sum_density")
def grid_sum_density(ctx: GridContext, gdf: gpd.GeoDataFrame, field: str) -> np.ndarray:
    return (grid_sum(ctx, gdf, field) / ctx.areas_km2).astype(np.float32)


@method("grid_ratio")
def grid_ratio(ctx: GridContext, gdf: gpd.GeoDataFrame, num: list[str], den: list[str], min_den: float = 0) -> np.ndarray:
    num_s = sum(_col(gdf, c) for c in num)
    den_s = sum(_col(gdf, c) for c in den)
    s = _sum_by_cell(ctx, gdf, {"num": num_s, "den": den_s})
    with np.errstate(divide="ignore", invalid="ignore"):
        r = s["num"] / s["den"]
    r[s["den"] < max(min_den, 1e-9)] = np.nan  # secret statistique / petits effectifs
    return r.astype(np.float32)


def _areal_weights(ctx: GridContext, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Intersections hexagone x polygone source, avec la part de surface de la source."""
    src = gdf.to_crs(grid.L93).reset_index(drop=True)
    src["_src_area"] = src.geometry.area
    src["_src"] = np.arange(len(src))
    hexes = ctx.polygons.to_crs(grid.L93)
    hexes["_pos"] = np.arange(ctx.n)
    inter = gpd.overlay(hexes[["_pos", "geometry"]], src, how="intersection", keep_geom_type=True)
    inter["_w"] = inter.geometry.area / inter["_src_area"]
    return inter


@method("grid_areal_density")
def grid_areal_density(ctx: GridContext, gdf: gpd.GeoDataFrame, field: str, unit_factor: float = 1.0, **_: Any) -> np.ndarray:
    """Valeur d'une grille grossière (1 km) répartie au prorata des surfaces, par km²."""
    inter = _areal_weights(ctx, gdf)
    acc = np.zeros(ctx.n)
    np.add.at(acc, inter["_pos"].values, _col(inter, field).values * unit_factor * inter["_w"].values)
    return (acc / ctx.areas_km2).astype(np.float32)


@method("grid_areal_ratio")
def grid_areal_ratio(ctx: GridContext, gdf: gpd.GeoDataFrame, num: str, den: str, min_den: float = 0, unit_factor: float = 1.0, **_: Any) -> np.ndarray:
    inter = _areal_weights(ctx, gdf)
    n = np.zeros(ctx.n)
    d = np.zeros(ctx.n)
    np.add.at(n, inter["_pos"].values, _col(inter, num).values * unit_factor * inter["_w"].values)
    np.add.at(d, inter["_pos"].values, _col(inter, den).values * unit_factor * inter["_w"].values)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = n / d
    r[d < max(min_den, 1e-9)] = np.nan
    return r.astype(np.float32)


def _subdivide(geoms: np.ndarray, max_vertices: int = 256) -> np.ndarray:
    """Découpe les grands polygones en morceaux, pour que l'intersection avec
    un hexagone ne parcoure pas des centaines de milliers de sommets."""
    done: list[np.ndarray] = []
    todo = shapely.get_parts(geoms)
    for _ in range(24):
        big = shapely.get_num_coordinates(todo) > max_vertices
        done.append(todo[~big])
        todo = todo[big]
        if not len(todo):
            break
        x0, y0, x1, y1 = shapely.bounds(todo).T
        wide = (x1 - x0) >= (y1 - y0)
        xm = np.where(wide, (x0 + x1) / 2, x1)
        ym = np.where(wide, y1, (y0 + y1) / 2)
        a = shapely.box(x0, y0, xm, ym)
        b = shapely.box(np.where(wide, xm, x0), np.where(wide, y0, ym), x1, y1)
        parts = shapely.get_parts(np.concatenate([shapely.intersection(todo, a), shapely.intersection(todo, b)]))
        todo = parts[shapely.get_dimensions(parts) == 2]
    return np.concatenate([*done, todo])


@method("polygon_share")
def polygon_share(ctx: GridContext, gdf: gpd.GeoDataFrame, **_: Any) -> np.ndarray:
    """Part de la surface de chaque hexagone couverte par l'union des polygones."""
    geoms = shapely.get_parts(gdf.to_crs(grid.L93).geometry.make_valid().values)
    # make_valid peut rendre des collections : on les ouvre et on ne garde que les surfaces.
    geoms = shapely.get_parts(geoms)
    pieces = _subdivide(geoms[shapely.get_dimensions(geoms) == 2])
    hexes = ctx.polygons.to_crs(grid.L93).geometry.values
    ih, ip = shapely.STRtree(pieces).query(hexes, predicate="intersects")
    covered = np.zeros(ctx.n)
    if len(ih):
        order = np.argsort(ih, kind="stable")
        ih, ip = ih[order], ip[order]
        inter = shapely.intersection(hexes[ih], pieces[ip])
        # Union par hexagone : les zonages se recouvrent (ZSC et ZPS, par exemple).
        starts = np.flatnonzero(np.r_[True, np.diff(ih) > 0])
        for s, e in zip(starts, np.r_[starts[1:], len(ih)]):
            covered[ih[s]] = shapely.area(inter[s] if e - s == 1 else shapely.union_all(inter[s:e]))
    return np.clip(covered / shapely.area(hexes), 0, 1).astype(np.float32)


@method("commune_spread_density")
def commune_spread_density(
    ctx: GridContext,
    df: pd.DataFrame,
    field: str,
    commune_col: str = "codeinseecommune",
    factor: float = 1.0,
    filter: dict[str, list[str]] | None = None,
) -> np.ndarray:
    """Valeur publiée par commune, répartie uniformément sur ses hexagones, par km²."""
    if ctx.communes is None or ctx.cell_commune is None:
        raise ValueError("commune_spread_density demande les contours communaux (admin_express)")
    for col, allowed in (filter or {}).items():
        lower = {c.lower(): c for c in df.columns}
        df = df[df[lower[col.lower()]].astype(str).isin(allowed)]
    lower = {c.lower(): c for c in df.columns}
    per_commune = (_col(df, field) * factor).groupby(df[lower[commune_col.lower()]].astype(str)).sum()
    code_to_pos = {c: i for i, c in enumerate(ctx.communes["code"].astype(str))}
    totals = np.zeros(len(ctx.communes))
    for code, v in per_commune.items():
        if code in code_to_pos:
            totals[code_to_pos[code]] += v
    cc = ctx.cell_commune
    counts = np.bincount(cc[cc >= 0], minlength=len(ctx.communes)).astype(float)
    out = np.full(ctx.n, np.nan)
    ok = cc >= 0
    out[ok] = totals[cc[ok]] / np.maximum(counts[cc[ok]], 1) / ctx.areas_km2[ok]
    return out.astype(np.float32)


def compute(ctx: GridContext, indicator: dict[str, Any], data: Any, source: dict[str, Any]) -> np.ndarray:
    fn = METHODS[indicator["method"]]
    params = dict(indicator.get("params", {}))
    if "unit_factor" in source and indicator["method"].startswith("grid_areal"):
        params.setdefault("unit_factor", source["unit_factor"])
    # Les noms de colonnes du registre passent par la table de correspondance de la source.
    cols = {k.lower(): v for k, v in (source.get("columns") or {}).items()}
    def remap(v):
        if isinstance(v, str):
            return cols.get(v.lower(), v)
        if isinstance(v, list):
            return [remap(x) for x in v]
        return v
    params = {k: (remap(v) if k in ("field", "num", "den") else v) for k, v in params.items()}
    return fn(ctx, data, **params)
