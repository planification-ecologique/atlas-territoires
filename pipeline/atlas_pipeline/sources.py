"""Téléchargement et lecture des sources brutes."""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import requests

from .registry import PIPELINE_DIR

CACHE = PIPELINE_DIR / "cache" / "raw"
VECTOR_EXT = (".gpkg", ".shp", ".geojson", ".fgb", ".parquet")


def _download(url: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = url.split("?")[0].rstrip("/").split("/")[-1] or "data"
    if "exports/csv" in url:
        name = "export.csv"
    dest = dest_dir / name
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    print(f"  téléchargement {url}")
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
        tmp.rename(dest)
    return dest


def _extract(path: Path) -> Path:
    if path.suffix == ".zip":
        out = path.with_suffix("")
        if not out.exists():
            with zipfile.ZipFile(path) as z:
                z.extractall(out)
        return out
    if path.suffix == ".7z":
        out = path.with_suffix("")
        if not out.exists():
            if not shutil.which("7z"):
                raise RuntimeError("7z est nécessaire pour ADMIN EXPRESS (brew install p7zip / apt install p7zip-full)")
            subprocess.run(["7z", "x", f"-o{out}", str(path)], check=True, stdout=subprocess.DEVNULL)
        return out
    return path


def fetch(source_id: str, source: dict[str, Any]) -> list[Path]:
    """Télécharge (si besoin) et renvoie les chemins locaux de la source.

    Un fichier déposé à la main dans pipeline/cache/raw/<id>/ est utilisé tel
    quel : c'est la voie à suivre quand `url` est vide.
    """
    d = CACHE / source_id
    urls = source.get("urls") or ([source["url"]] if source.get("url") else [])
    if not urls:
        local = [p for p in d.glob("*") if not p.name.endswith(".part")] if d.exists() else []
        if not local:
            raise FileNotFoundError(
                f"Source '{source_id}' sans URL : télécharger le fichier depuis {source.get('page')} "
                f"et le déposer dans {d}/"
            )
        return [_extract(p) for p in local]
    return [_extract(_download(u, d)) for u in urls]


def _vector_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*") if p.suffix.lower() in VECTOR_EXT)


def read_vector(paths: list[Path], bbox_wgs84: tuple[float, float, float, float], layer: str | None = None) -> gpd.GeoDataFrame:
    """Lit et concatène des fichiers vecteur, limités à l'emprise de la région."""
    frames = []
    for p in paths:
        for f in _vector_files(p):
            if layer and layer.lower() not in f.stem.lower():
                continue
            g = gpd.read_file(f, bbox=_bbox_in_crs(f, bbox_wgs84))
            if len(g):
                frames.append(g.to_crs("EPSG:4326"))
    if not frames:
        raise FileNotFoundError(f"aucune donnée vecteur trouvée dans {paths}")
    return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:4326")


def _bbox_in_crs(path: Path, bbox_wgs84):
    import pyogrio
    from pyproj import Transformer

    crs = pyogrio.read_info(path).get("crs")
    if not crs:
        return bbox_wgs84
    t = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    xs, ys = t.transform([bbox_wgs84[0], bbox_wgs84[2]], [bbox_wgs84[1], bbox_wgs84[3]])
    return (min(xs), min(ys), max(xs), max(ys))


def read_table(paths: list[Path], source: dict[str, Any]) -> pd.DataFrame:
    files = [f for p in paths for f in ([p] if p.is_file() else p.rglob("*.csv"))]
    return pd.concat([pd.read_csv(f, sep=source.get("sep", ","), low_memory=False) for f in files], ignore_index=True)
