"""Point d'entrée : python -m atlas_pipeline <commande>."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .registry import ROOT, load_registry

DEFAULT_OUT = ROOT / "web" / "public" / "data"


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="atlas_pipeline", description="Pipeline de l'atlas des territoires")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check", help="valide le registre (indicateurs, paires, sources)")

    d = sub.add_parser("demo", help="génère le jeu de démonstration synthétique")
    d.add_argument("--region", default="24")
    d.add_argument("--res", type=int, default=8)
    d.add_argument("--out", type=Path, default=DEFAULT_OUT)

    b = sub.add_parser("build", help="construit les indicateurs depuis les sources réelles")
    b.add_argument("--region", default="24")
    b.add_argument("--res", type=int, default=8)
    b.add_argument("--out", type=Path, default=DEFAULT_OUT)
    b.add_argument("--only", nargs="*", help="limiter à ces indicateurs")
    b.add_argument("--strict", action="store_true", help="échouer si une source manque")

    rc = sub.add_parser("reclassify", help="recalcule classes et paires depuis les valeurs déjà construites (après un changement de seuils)")
    rc.add_argument("--region", default="24")
    rc.add_argument("--out", type=Path, default=DEFAULT_OUT)

    r = sub.add_parser("report", help="affiche les paires d'une région déjà construite")
    r.add_argument("--region", default="24")
    r.add_argument("--out", type=Path, default=DEFAULT_OUT)

    args = p.parse_args(argv)
    reg = load_registry()

    if args.cmd == "check":
        print(f"Registre valide : {len(reg.indicators)} indicateurs, {len(reg.pairs)} paires, {len(reg.regions)} région(s).")
    elif args.cmd == "demo":
        from .demo import build_demo
        m = build_demo(reg, args.out, args.region, args.res)
        _summary(reg, m)
    elif args.cmd == "build":
        from .build import build_region
        m = build_region(reg, args.region, args.res, args.out, args.only, skip_missing=not args.strict)
        _summary(reg, m)
    elif args.cmd == "reclassify":
        m = _reclassify(reg, args.region, args.out)
        _summary(reg, m)
    elif args.cmd == "report":
        m = json.loads((args.out / args.region / "manifest.json").read_text(encoding="utf-8"))
        _summary(reg, m)


def _reclassify(reg, region: str, out: Path) -> dict:
    import numpy as np

    from . import grid
    from .export import write_region, write_registry

    old = json.loads((out / region / "manifest.json").read_text(encoding="utf-8"))
    rdir = out / region / f"r{old['res']}"
    cells = np.fromfile(rdir / "cells.u64", dtype="<u8")
    values = {
        i["id"]: np.fromfile(rdir / f"{i['id']}.f32", dtype="<f4")
        for i in reg.indicators
        if (rdir / f"{i['id']}.f32").exists()
    }
    write_registry(reg, out)
    return write_region(
        reg, out, region, old["res"], cells, grid.cell_areas_km2(cells), values,
        synthetic=old.get("synthetic", False), places=old.get("places"),
    )


def _summary(reg, m) -> None:
    tag = " (DONNÉES SYNTHÉTIQUES)" if m.get("synthetic") else ""
    print(f"\n{m['name']}{tag} : {m['cells']:,} hexagones r{m['res']}, {m['area_km2']:,.0f} km²".replace(",", " "))
    titles = {p["id"]: (p["type"], p["title"]) for p in reg.pairs}
    rows = sorted(m["pairs"].items(), key=lambda kv: -kv[1]["hectares"])
    for pid, s in rows:
        t, title = titles[pid]
        res = f", {s['residents']:,.0f} hab".replace(",", " ") if "residents" in s else ""
        print(f"  {t:8} {s['hectares']:>9,.0f} ha ({s['share']:.1%}){res}  {title}".replace(",", " "))


if __name__ == "__main__":
    main()
