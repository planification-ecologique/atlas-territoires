"""Téléchargement et lecture des sources brutes."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import quote

import geopandas as gpd
import pandas as pd
import pyogrio
import requests
from pyproj import Transformer

from .registry import PIPELINE_DIR

CACHE = PIPELINE_DIR / "cache" / "raw"
RETRIES = 4         # nouveaux essais après une erreur réseau ou serveur
RETRY_WAIT = 30     # secondes, doublées à chaque essai
VECTOR_EXT = (".gpkg", ".shp", ".geojson", ".fgb", ".parquet", ".gml")


def _download(url: str, dest_dir: Path, name: str | None = None) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    if name is None:
        name = url.split("?")[0].rstrip("/").split("/")[-1] or "data"
        if "exports/csv" in url:
            name = "export.csv"
    dest = dest_dir / name
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    print(f"  téléchargement {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(RETRIES + 1):
        try:
            with requests.get(url, stream=True, timeout=600) as r:
                r.raise_for_status()
                # Certains serveurs (INPN) répondent une page d'erreur HTML avec un code 200.
                if "text/html" in r.headers.get("content-type", ""):
                    raise RuntimeError(f"{url} renvoie une page HTML au lieu de données")
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
            break
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError, requests.exceptions.ChunkedEncodingError) as e:
            # Les WFS (Géorisques surtout) expirent ou renvoient des 5xx de temps à autre.
            status = getattr(getattr(e, "response", None), "status_code", None)
            if attempt == RETRIES or (status is not None and status < 500):
                raise
            wait = RETRY_WAIT * 2**attempt
            print(f"  nouvel essai dans {wait} s ({e.__class__.__name__})")
            time.sleep(wait)
    tmp.rename(dest)
    if dest.suffix == ".geojson":
        _check_complete(dest)
    return dest


def _check_complete(path: Path) -> None:
    """Refuse une réponse WFS tronquée par la limite d'objets du serveur."""
    data = json.loads(path.read_text(encoding="utf-8"))
    matched, got = data.get("numberMatched"), len(data.get("features", []))
    if isinstance(matched, int) and matched > got:
        path.unlink()
        raise RuntimeError(f"réponse WFS tronquée : {got} objets sur {matched}")


def _download_by_id(url: str, dest_dir: Path, name: str, id_field: str) -> Path:
    """Lit un WFS objet par objet (GML), pour les couches aux géométries très lourdes.

    On liste d'abord les identifiants de l'emprise, sans géométrie, puis on
    demande chaque objet par son identifiant : la pagination par startIndex n'a
    pas d'ordre garanti (doublons, oublis) et finit par expirer.
    """
    out = dest_dir / name
    if out.exists():
        return out
    tmp = dest_dir / f"{name}.part"
    tmp.mkdir(parents=True, exist_ok=True)
    r = requests.get(f"{url}&propertyName={id_field}", timeout=600)
    r.raise_for_status()
    ids = sorted({int(x) for x in re.findall(rf"<ms:{id_field}>(\d+)<", r.text)})
    if not ids:
        raise RuntimeError(f"aucun objet '{id_field}' dans l'emprise : {url}")
    base = re.sub(r"&bbox=[^&]*", "", url)
    for i in ids:
        flt = (
            '<fes:Filter xmlns:fes="http://www.opengis.net/fes/2.0"><fes:PropertyIsEqualTo>'
            f"<fes:ValueReference>{id_field}</fes:ValueReference><fes:Literal>{i}</fes:Literal>"
            "</fes:PropertyIsEqualTo></fes:Filter>"
        )
        page = _download(f"{base}&filter={quote(flt)}", tmp, f"{i}.gml")
        if f"<ms:{id_field}>{i}<".encode() not in page.read_bytes():
            page.unlink()
            raise RuntimeError(f"objet {i} absent de la réponse WFS")
    tmp.rename(out)
    return out


def _extract(path: Path, members: list[str] | None = None) -> Path:
    """Décompresse une archive ; `members` limite aux fichiers de ces noms."""
    if path.suffix == ".zip":
        out = path.with_suffix("")
        if not out.exists():
            with zipfile.ZipFile(path) as z:
                names = [n for n in z.namelist() if not members or Path(n).name in members]
                z.extractall(out, names)
        return out
    if path.suffix == ".7z":
        out = path.with_suffix("")
        if not out.exists():
            if not shutil.which("7z"):
                raise RuntimeError("7z est nécessaire pour ADMIN EXPRESS (brew install p7zip / apt install p7zip-full)")
            only = [f"-ir!{m}" for m in members or []]
            subprocess.run(["7z", "x", f"-o{out}", str(path), *only], check=True, stdout=subprocess.DEVNULL)
        return out
    return path


def fetch(
    source_id: str,
    source: dict[str, Any],
    region: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> list[Path]:
    """Télécharge (si besoin) et renvoie les chemins locaux de la source.

    Un fichier déposé à la main dans pipeline/cache/raw/<id>/ est utilisé tel
    quel : c'est la voie à suivre quand `url` est vide.

    Une URL de service (WFS) peut contenir {west}, {south}, {east}, {north},
    remplacés par l'emprise de la région ; `filenames` donne alors le nom du
    fichier en cache, où {region} est remplacé par le code de la région.
    """
    d = CACHE / source_id
    urls = source.get("urls") or ([source["url"]] if source.get("url") else [])
    if not urls:
        local = [p for p in d.glob("*") if p.suffix != ".part"] if d.exists() else []
        if not local:
            raise FileNotFoundError(
                f"Source '{source_id}' sans URL : télécharger le fichier depuis {source.get('page')} "
                f"et le déposer dans {d}/"
            )
        return [_extract(p, source.get("extract")) for p in local if not (p.is_dir() and _has_archive(p))]
    names: list[str | None] = list(source.get("filenames") or [None] * len(urls))
    if len(names) != len(urls):
        raise ValueError(f"source '{source_id}' : autant de `filenames` que d'URL sont attendus")
    if region is not None:
        # {region} : code Insee de la région (archives régionales, ex. RPG).
        urls = [u.replace("{region}", region) for u in urls]
    if any("{west}" in u for u in urls):
        if bbox is None or region is None:
            raise ValueError(f"source '{source_id}' : l'URL demande une région et son emprise")
        w, s, e, n = bbox
        urls = [u.format(west=w, south=s, east=e, north=n) for u in urls]
        names = [x and x.format(region=region) for x in names]
    if source.get("by_id"):
        return [_download_by_id(u, d, x or "objets", source["by_id"]) for u, x in zip(urls, names)]
    return [_extract(_download(u, d, x), source.get("extract")) for u, x in zip(urls, names)]


def _has_archive(folder: Path) -> bool:
    """Vrai si ce dossier est l'extraction d'une archive voisine (à ne pas lire deux fois)."""
    return any(folder.with_name(folder.name + ext).exists() for ext in (".zip", ".7z"))


def _vector_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*") if p.suffix.lower() in VECTOR_EXT)


def _layers(path: Path, layer: str | None) -> list[str | None]:
    """Couches à lire dans un fichier : toutes, ou celle demandée (nom exact dans un GeoPackage)."""
    if path.suffix.lower() != ".gpkg":
        return [None] if not layer or layer.lower() in path.stem.lower() else []
    names = [str(n) for n, geom in pyogrio.list_layers(path) if geom is not None]
    return [n for n in names if not layer or n.lower() == layer.lower()]


def read_vector(paths: list[Path], bbox_wgs84: tuple[float, float, float, float], layer: str | None = None) -> gpd.GeoDataFrame:
    """Lit et concatène des fichiers vecteur, limités à l'emprise de la région."""
    frames = []
    for p in paths:
        for f in _vector_files(p):
            for name in _layers(f, layer):
                g = gpd.read_file(f, bbox=_bbox_in_crs(f, bbox_wgs84, name), layer=name, engine="pyogrio", **_open_options(f))
                if len(g):
                    frames.append(g.to_crs("EPSG:4326"))
    if not frames:
        raise FileNotFoundError(f"aucune donnée vecteur trouvée dans {paths}")
    return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:4326")


def _open_options(path: Path) -> dict[str, str]:
    """GML : sans cela, GDAL redemande le schéma XSD au serveur à chaque ouverture."""
    return {"DOWNLOAD_SCHEMA": "NO"} if path.suffix.lower() == ".gml" else {}


def _bbox_in_crs(path: Path, bbox_wgs84, layer: str | None = None):
    crs = pyogrio.read_info(path, layer=layer, **_open_options(path)).get("crs")
    if not crs:
        return bbox_wgs84
    # Les bords sont densifiés : en projection (Lambert-93, LAEA) l'emprise est
    # inclinée et ses deux coins ne suffisent pas à la contenir.
    return Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform_bounds(*bbox_wgs84, densify_pts=21)


def read_table(paths: list[Path], source: dict[str, Any]) -> pd.DataFrame:
    files = [f for p in paths for f in ([p] if p.is_file() else p.rglob("*.csv"))]
    return pd.concat([pd.read_csv(f, sep=source.get("sep", ","), low_memory=False) for f in files], ignore_index=True)
