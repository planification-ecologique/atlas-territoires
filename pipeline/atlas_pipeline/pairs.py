"""Calcul des recouvrements pour les paires de conflits et de synergies.

La même logique tourne dans le navigateur (web/src/lib/pairs.ts) ; ce module
sert aux rapports et aux tests.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .classify import end_mask


def pair_mask(pair: dict[str, Any], values: dict[str, np.ndarray], classes: dict[str, np.ndarray], indicators: dict[str, dict]) -> np.ndarray:
    masks = []
    for side in ("a", "b"):
        s = pair[side]
        ind = indicators[s["indicator"]]
        masks.append(end_mask(values[s["indicator"]], classes[s["indicator"]], ind[s["end"]], s["end"]))
    return masks[0] & masks[1]


def pair_stats(mask: np.ndarray, areas_km2: np.ndarray, residents: np.ndarray | None) -> dict[str, float]:
    ha = float(areas_km2[mask].sum() * 100)
    total_ha = float(areas_km2.sum() * 100)
    out = {"cells": int(mask.sum()), "hectares": ha, "share": ha / total_ha if total_ha else 0.0}
    if residents is not None:
        out["residents"] = float(np.nansum(residents[mask]))
    return out
