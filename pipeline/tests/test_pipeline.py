import json

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Point, box

from atlas_pipeline import grid
from atlas_pipeline.classify import breaks_for, classify, end_mask
from atlas_pipeline.indicators import GridContext, METHODS
from atlas_pipeline.pairs import pair_mask, pair_stats
from atlas_pipeline.registry import load_registry


@pytest.fixture(scope="module")
def ctx():
    # Petit carré autour de Blois, résolution 8.
    area = box(1.30, 47.57, 1.36, 47.61)
    cells = grid.cells_for_polygon(area, 8)
    return GridContext(8, cells, grid.cell_areas_km2(cells), grid.cell_polygons(cells))


def test_registry_is_valid():
    reg = load_registry()
    assert len(reg.indicators) >= 10
    assert all(p["question"] for p in reg.pairs)
    assert reg.weight_indicator == "pop_habitants"


def test_grid_is_sorted_and_lookup_works(ctx):
    assert ctx.n > 20
    assert np.all(np.diff(ctx.cells.astype(np.int64)) > 0)
    pos = grid.lookup(ctx.cells, ctx.cells[[3, 7]])
    assert pos.tolist() == [3, 7]
    assert grid.lookup(ctx.cells, np.array([0], dtype=np.uint64)).tolist() == [-1]


def test_polygon_share_full_and_partial(ctx):
    full = gpd.GeoDataFrame(geometry=[box(1.0, 47.0, 2.0, 48.0)], crs="EPSG:4326")
    share = METHODS["polygon_share"](ctx, full)
    assert np.allclose(share, 1.0, atol=1e-3)
    west = gpd.GeoDataFrame(geometry=[box(1.0, 47.0, 1.33, 48.0)], crs="EPSG:4326")
    share = METHODS["polygon_share"](ctx, west)
    assert 0.3 < share.mean() < 0.7


def test_grid_sum_conserves_totals(ctx):
    centers = grid.cell_centers(ctx.cells)
    pts = gpd.GeoDataFrame(
        {"ind": np.full(len(centers), 10.0)},
        geometry=[Point(x, y).buffer(0.0005) for x, y in centers],
        crs="EPSG:4326",
    )
    s = METHODS["grid_sum"](ctx, pts, field="ind")
    assert s.sum() == pytest.approx(10.0 * ctx.n)


def test_grid_ratio_masks_small_counts(ctx):
    centers = grid.cell_centers(ctx.cells)
    pts = gpd.GeoDataFrame(
        {"men": [5.0, 50.0] * (len(centers) // 2) + [50.0] * (len(centers) % 2), "men_pauv": 5.0},
        geometry=[Point(x, y) for x, y in centers],
        crs="EPSG:4326",
    )
    r = METHODS["grid_ratio"](ctx, pts, num=["men_pauv"], den=["men"], min_den=10)
    assert np.isnan(r[0]) and r[1] == pytest.approx(0.1)


def test_areal_density_conserves_mass(ctx):
    # Une maille de 1 km² portant 10 000 m² (= 1 ha) consommés.
    sq = gpd.GeoDataFrame({"naf": [10000.0]}, geometry=[box(1.325, 47.585, 1.338, 47.594)], crs="EPSG:4326")
    d = METHODS["grid_areal_density"](ctx, sq, field="naf", unit_factor=0.0001)
    assert (d * ctx.areas_km2).sum() == pytest.approx(1.0, rel=1e-3)


def test_classify_and_quantiles_with_zeros():
    v = np.array([0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, np.nan], dtype=np.float32)
    ind = {"classes": "quantiles"}
    br = breaks_for(v, ind)
    c = classify(v, br)
    assert c[-1] == 0  # pas de donnée
    assert set(c[:7]) == {1}  # les zéros restent en classe 1
    assert c[-2] == 5


def test_pair_logic_matches_expectation():
    vals = {"a": np.array([1, 5, 9, 9], dtype=np.float32), "b": np.array([9, 9, 1, 9], dtype=np.float32)}
    cls = {k: classify(v, [2, 4, 6, 8]) for k, v in vals.items()}
    inds = {"a": {"high": {"value": 5}}, "b": {"high": {"class_min": 5}}}
    pair = {"a": {"indicator": "a", "end": "high"}, "b": {"indicator": "b", "end": "high"}}
    m = pair_mask(pair, vals, cls, inds)
    assert m.tolist() == [False, True, False, True]
    s = pair_stats(m, np.ones(4), np.array([1, 2, 3, 4], dtype=np.float32))
    assert s == {"cells": 2, "hectares": 200.0, "share": 0.5, "residents": 6.0}
    assert end_mask(vals["a"], cls["a"], {"value": 1}, "low").tolist() == [True, False, False, False]


def test_demo_export(tmp_path):
    from atlas_pipeline.demo import build_demo

    reg = load_registry()
    m = build_demo(reg, tmp_path, res=6)  # résolution grossière pour aller vite
    n = m["cells"]
    cells = np.fromfile(tmp_path / "24" / "r6" / "cells.u64", dtype="<u8")
    assert len(cells) == n and m["synthetic"] is True
    for ind in reg.indicators:
        assert len(np.fromfile(tmp_path / "24" / "r6" / f"{ind['id']}.f32", dtype="<f4")) == n
        assert len(np.fromfile(tmp_path / "24" / "r6" / f"{ind['id']}.c8", dtype="u1")) == n
    registry = json.loads((tmp_path / "registry.json").read_text())
    assert {p["id"] for p in registry["pairs"]} == set(m["pairs"])


def test_polygon_share_counts_overlaps_once(ctx):
    west = box(1.0, 47.0, 1.33, 48.0)
    one = METHODS["polygon_share"](ctx, gpd.GeoDataFrame(geometry=[west], crs="EPSG:4326"))
    twice = METHODS["polygon_share"](ctx, gpd.GeoDataFrame(geometry=[west, west], crs="EPSG:4326"))
    assert np.allclose(one, twice, atol=1e-6)


def test_subdivide_conserves_area():
    from atlas_pipeline.indicators import _subdivide

    disc = Point(0, 0).buffer(1000, quad_segs=2000).difference(Point(100, 0).buffer(300, quad_segs=500))
    pieces = _subdivide(np.array([disc]))
    assert len(pieces) > 10
    assert sum(p.area for p in pieces) == pytest.approx(disc.area)
    assert max(p.exterior.coords.__len__() for p in pieces) <= 256


def test_read_vector_layer_and_projected_bbox(tmp_path):
    from atlas_pipeline.sources import read_vector

    # Coins nord-ouest et sud-est de la région : hors de l'emprise si l'on ne projette que deux coins.
    pts = gpd.GeoDataFrame({"k": [1, 2]}, geometry=[Point(0.06, 48.94), Point(3.12, 46.35)], crs="EPSG:4326").to_crs("EPSG:3035")
    f = tmp_path / "x.gpkg"
    pts.to_file(f, layer="bonne")
    pts.to_file(f, layer="bonne_bis")
    assert len(read_vector([f], (0.05, 46.34, 3.13, 48.95), layer="BONNE")) == 2


def test_fetch_refuses_html_error_pages(tmp_path, monkeypatch):
    from atlas_pipeline import sources

    class Page:
        headers = {"content-type": "text/html;charset=UTF-8"}
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def raise_for_status(self): pass

    monkeypatch.setattr(sources, "CACHE", tmp_path)
    monkeypatch.setattr(sources.requests, "get", lambda *a, **k: Page())
    with pytest.raises(RuntimeError, match="HTML"):
        sources.fetch("x", {"url": "https://example.org/sic.zip"})
