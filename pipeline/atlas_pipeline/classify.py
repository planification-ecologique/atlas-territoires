"""Classement en 5 classes et seuils "haut" / "bas" des paires.

Classes stockées en uint8 : 0 = pas de donnée, 1 à 5 = de la plus basse à la
plus haute.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def breaks_for(values: np.ndarray, indicator: dict[str, Any]) -> list[float]:
    if indicator["classes"] == "seuils":
        return [float(b) for b in indicator["breaks"]]
    v = values[np.isfinite(values)]
    # Les distributions très concentrées sur zéro (consommation, EnR) : les
    # quantiles portent sur les valeurs strictement positives, zéro reste en classe 1.
    pos = v[v > 0]
    base = pos if len(pos) >= 10 and len(pos) < 0.8 * len(v) else v
    if len(base) == 0:
        return [0.0, 0.0, 0.0, 0.0]
    qs = [0.2, 0.4, 0.6, 0.8] if base is v else [0.0, 0.33, 0.66, 0.9]
    return [float(x) for x in np.quantile(base, qs)]


def classify(values: np.ndarray, breaks: list[float]) -> np.ndarray:
    out = np.zeros(len(values), dtype=np.uint8)
    ok = np.isfinite(values)
    # value <= b1 -> 1 ; b1 < value <= b2 -> 2 ; ... ; > b4 -> 5
    out[ok] = (np.searchsorted(np.asarray(breaks), values[ok], side="left") + 1).astype(np.uint8)
    return out


def end_mask(values: np.ndarray, classes: np.ndarray, rule: dict[str, Any], end: str) -> np.ndarray:
    """Hexagones à l'extrémité `end` ('high' ou 'low') selon la règle du registre."""
    ok = classes > 0
    if "value" in rule:
        v = rule["value"]
        with np.errstate(invalid="ignore"):
            m = values >= v if end == "high" else values <= v
        return m & ok
    if "class_min" in rule:
        return (classes >= rule["class_min"]) & ok
    if "class_max" in rule:
        return (classes <= rule["class_max"]) & ok
    raise ValueError(f"règle de seuil inconnue : {rule}")
