"""Écriture des fichiers statiques lus par l'application.

Format (voir docs/format-donnees.md) :
  <out>/registry.json                      indicateurs + paires + thèmes
  <out>/<region>/manifest.json             métadonnées, seuils, statistiques
  <out>/<region>/r<res>/cells.json         cellules H3 triées, uint64 little-endian
  <out>/<region>/r<res>/<id>.json          valeurs float32 (NaN = pas de donnée)
                                           et classes uint8 (0 = pas de donnée, 1..5)

Les tableaux sont des octets little-endian encodés en base64 dans du JSON : les
proxys d'administration (postes SPM) refusent les fichiers binaires (.u64, .f32).
"""

from __future__ import annotations

import base64
import json
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from .classify import breaks_for, classify
from .pairs import pair_mask, pair_stats
from .registry import Registry


def pack(a: np.ndarray, dtype: str) -> dict[str, Any]:
    """Tableau numpy -> {dtype, length, base64} (octets little-endian)."""
    a = np.ascontiguousarray(a, dtype=dtype)
    return {"dtype": dtype, "length": int(len(a)), "base64": base64.b64encode(a.tobytes()).decode("ascii")}


def unpack(d: dict[str, Any]) -> np.ndarray:
    a = np.frombuffer(base64.b64decode(d["base64"]), dtype=d["dtype"])
    if len(a) != d["length"]:
        raise ValueError(f"tableau tronqué : {len(a)} valeurs sur {d['length']}")
    return a


def write_array(path: Path, a: np.ndarray, dtype: str) -> None:
    path.write_text(json.dumps(pack(a, dtype)), encoding="utf-8")


def read_array(path: Path) -> np.ndarray:
    return unpack(json.loads(path.read_text(encoding="utf-8")))


def read_layer(path: Path) -> tuple[np.ndarray, np.ndarray]:
    d = json.loads(path.read_text(encoding="utf-8"))
    return unpack(d["values"]), unpack(d["classes"])


def write_registry(reg: Registry, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "themes": reg.themes,
        "indicators": [
            {k: v for k, v in i.items() if k not in ("params", "method")} | {
                "source": {
                    "id": i["source"],
                    "label": reg.sources[i["source"]]["label"],
                    "licence": reg.sources[i["source"]].get("licence"),
                    "page": reg.sources[i["source"]].get("page"),
                }
            }
            for i in reg.indicators
        ],
        "pairs": reg.pairs,
        "regions": reg.regions,
    }
    (out / "registry.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def write_region(
    reg: Registry,
    out: Path,
    region: str,
    res: int,
    cells: np.ndarray,
    areas_km2: np.ndarray,
    values: dict[str, np.ndarray],
    *,
    synthetic: bool = False,
    places: list[dict[str, Any]] | None = None,
    bbox: list[float] | None = None,
) -> dict[str, Any]:
    rdir = out / region / f"r{res}"
    rdir.mkdir(parents=True, exist_ok=True)
    write_array(rdir / "cells.json", cells, "<u8")

    indicators = {i["id"]: i for i in reg.indicators}
    classes: dict[str, np.ndarray] = {}
    meta_ind: dict[str, Any] = {}
    for ind_id, v in values.items():
        ind = indicators[ind_id]
        v = v.astype(np.float32)
        br = breaks_for(v, ind)
        c = classify(v, br)
        classes[ind_id] = c
        layer = {"values": pack(v, "<f4"), "classes": pack(c, "u1")}
        (rdir / f"{ind_id}.json").write_text(json.dumps(layer), encoding="utf-8")
        finite = v[np.isfinite(v)]
        meta_ind[ind_id] = {
            "breaks": br,
            "coverage": float(len(finite) / len(v)) if len(v) else 0.0,
            "min": float(finite.min()) if len(finite) else None,
            "max": float(finite.max()) if len(finite) else None,
            "mean": float(finite.mean()) if len(finite) else None,
        }

    weight = reg.weight_indicator
    residents = values.get(weight) if weight else None
    pair_out = {}
    for p in reg.pairs:
        if p["a"]["indicator"] in values and p["b"]["indicator"] in values:
            m = pair_mask(p, values, classes, indicators)
            pair_out[p["id"]] = pair_stats(m, areas_km2, residents)

    manifest = {
        "region": region,
        "name": reg.regions[region]["name"],
        "res": res,
        "cells": int(len(cells)),
        "area_km2": float(areas_km2.sum()),
        "synthetic": synthetic,
        "built": date.today().isoformat(),
        "indicators": meta_ind,
        "pairs": pair_out,
        "places": places or [],
        "bbox": [round(float(x), 4) for x in (bbox or reg.regions[region]["bbox"])],
    }
    (out / region / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    write_index(reg, out)
    return manifest


def write_index(reg: Registry, out: Path) -> list[dict[str, Any]]:
    """Liste des régions construites, lue par l'application pour son sélecteur."""
    items = []
    for code in reg.regions:
        mf = out / code / "manifest.json"
        if mf.exists():
            m = json.loads(mf.read_text(encoding="utf-8"))
            items.append({"code": code, "name": m["name"], "cells": m["cells"], "synthetic": m.get("synthetic", False)})
    # Ordre alphabétique sans tenir compte des accents (sinon « Île-de-France » passe après « Provence »).
    items.sort(key=lambda r: unicodedata.normalize("NFD", r["name"]).encode("ascii", "ignore").decode().lower())
    (out / "index.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    return items
