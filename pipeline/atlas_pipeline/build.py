"""Construction des indicateurs d'une région à partir des sources réelles."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from . import grid, sources
from .export import write_region, write_registry
from .indicators import GridContext, compute
from .registry import Registry


def build_region(reg: Registry, region: str, res: int, out: Path, only: list[str] | None = None, skip_missing: bool = True) -> dict:
    r = reg.regions[region]
    bbox = tuple(r["bbox"])
    ae = reg.sources["admin_express"]
    print(f"[1/3] contours ADMIN EXPRESS, région {region} ({r['name']})")
    ae_paths = sources.fetch("admin_express", ae)
    regions = sources.read_vector(ae_paths, bbox, layer=ae["layers"]["regions"])
    code_col = next(c for c in regions.columns if c.lower() in ("insee_reg", "code_insee"))
    region_geom = regions.loc[regions[code_col].astype(str) == region].geometry.union_all()
    communes = sources.read_vector(ae_paths, bbox, layer=ae["layers"]["communes"])
    ccode = next(c for c in communes.columns if c.lower() in ("insee_com", "code_insee"))
    cname = next(c for c in communes.columns if c.lower() in ("nom", "nom_m", "nom_com"))
    communes = communes.rename(columns={ccode: "code", cname: "nom"})[["code", "nom", "geometry"]]

    print(f"[2/3] grille H3 r{res}")
    cells = grid.cells_for_polygon(region_geom, res)
    polys = grid.cell_polygons(cells)
    areas = grid.cell_areas_km2(cells)
    centers = grid.cell_centers(cells)
    import geopandas as gpd
    pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(centers[:, 0], centers[:, 1]), crs="EPSG:4326")
    communes = communes[communes.intersects(region_geom)].reset_index(drop=True)
    j = gpd.sjoin(pts, communes[["geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated()]
    cell_commune = j["index_right"].fillna(-1).astype(np.int32).values
    ctx = GridContext(res, cells, areas, polys, communes, cell_commune)
    print(f"  {len(cells):,} hexagones, {areas.sum():,.0f} km², {len(communes):,} communes".replace(",", " "))

    print("[3/3] indicateurs")
    values: dict[str, np.ndarray] = {}
    cache: dict[str, object] = {}
    for ind in reg.indicators:
        if only and ind["id"] not in only:
            continue
        sid = ind["source"]
        src = reg.sources[sid]
        try:
            if sid not in cache:
                paths = sources.fetch(sid, src)
                cache[sid] = sources.read_table(paths, src) if src.get("format") == "csv" else sources.read_vector(paths, bbox)
            values[ind["id"]] = compute(ctx, ind, cache[sid], src)
            print(f"  ✓ {ind['id']}")
        except Exception as e:  # noqa: BLE001
            if not skip_missing:
                raise
            print(f"  ✗ {ind['id']} ignoré : {e}")

    write_registry(reg, out)
    places = [
        {"name": n, "lng": float(g.centroid.x), "lat": float(g.centroid.y)}
        for n, g in zip(communes["nom"], communes.geometry)
    ]
    manifest = write_region(reg, out, region, res, cells, areas, values, places=places)
    (out / region / "communes.json").write_text(
        __import__("json").dumps({"codes": communes["code"].tolist(), "noms": communes["nom"].tolist()}, ensure_ascii=False),
        encoding="utf-8",
    )
    cell_commune.astype("<i4").tofile(out / region / f"r{res}" / "commune.i32")
    return manifest
