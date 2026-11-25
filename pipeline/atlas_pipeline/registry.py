"""Lecture et validation du registre (indicateurs, paires, sources)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_DIR = ROOT / "registry"
PIPELINE_DIR = ROOT / "pipeline"

ROLES = {"etat", "risque", "opportunite", "contrainte"}
PAIR_TYPES = {"conflit", "synergie"}
ENDS = {"high", "low"}


@dataclass
class Registry:
    themes: dict[str, str]
    indicators: list[dict[str, Any]]
    pairs: list[dict[str, Any]]
    regions: dict[str, dict[str, Any]]
    sources: dict[str, dict[str, Any]]

    def indicator(self, ind_id: str) -> dict[str, Any]:
        for ind in self.indicators:
            if ind["id"] == ind_id:
                return ind
        raise KeyError(ind_id)

    @property
    def weight_indicator(self) -> str | None:
        return next((i["id"] for i in self.indicators if i.get("weight")), None)


def _load(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_registry(registry_dir: Path = REGISTRY_DIR, pipeline_dir: Path = PIPELINE_DIR) -> Registry:
    ind = _load(registry_dir / "indicators.yaml")
    pairs = _load(registry_dir / "pairs.yaml")["pairs"]
    regions = _load(registry_dir / "regions.yaml")["regions"]
    sources = _load(pipeline_dir / "sources.yaml")
    reg = Registry(ind["themes"], ind["indicators"], pairs, regions, sources)
    validate(reg)
    return reg


def validate(reg: Registry) -> None:
    errors: list[str] = []
    ids = [i["id"] for i in reg.indicators]
    if len(ids) != len(set(ids)):
        errors.append("identifiants d'indicateurs en double")
    for i in reg.indicators:
        where = f"indicateur {i.get('id')}"
        for key in ("id", "label", "theme", "role", "unit", "method", "source", "classes"):
            if key not in i:
                errors.append(f"{where} : champ manquant '{key}'")
        if i.get("theme") not in reg.themes:
            errors.append(f"{where} : thème inconnu '{i.get('theme')}'")
        if i.get("role") not in ROLES:
            errors.append(f"{where} : rôle inconnu '{i.get('role')}'")
        if i.get("source") not in reg.sources:
            errors.append(f"{where} : source inconnue '{i.get('source')}'")
        if i.get("classes") == "seuils" and len(i.get("breaks", [])) != 4:
            errors.append(f"{where} : 'seuils' demande 4 valeurs dans 'breaks'")
    pair_ids = [p["id"] for p in reg.pairs]
    if len(pair_ids) != len(set(pair_ids)):
        errors.append("identifiants de paires en double")
    for p in reg.pairs:
        where = f"paire {p.get('id')}"
        if p.get("type") not in PAIR_TYPES:
            errors.append(f"{where} : type inconnu '{p.get('type')}'")
        for side in ("a", "b"):
            s = p.get(side, {})
            if s.get("indicator") not in ids:
                errors.append(f"{where} : indicateur inconnu '{s.get('indicator')}'")
                continue
            if s.get("end") not in ENDS:
                errors.append(f"{where} : extrémité inconnue '{s.get('end')}'")
                continue
            if s["end"] not in reg.indicator(s["indicator"]):
                errors.append(f"{where} : '{s['indicator']}' n'a pas de seuil '{s['end']}'")
        if not p.get("question"):
            errors.append(f"{where} : question manquante")
    if errors:
        raise ValueError("Registre invalide :\n- " + "\n- ".join(errors))
