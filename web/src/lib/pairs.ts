import type { End, EndRule, Indicator, Layer, PairSide } from "./types";

/**
 * Hexagones à l'extrémité "haut" ou "bas" d'un indicateur.
 * Même logique que pipeline/atlas_pipeline/classify.py:end_mask.
 */
export function endMask(layer: Layer, rule: EndRule, end: End): Uint8Array {
  const { values, classes } = layer;
  const n = classes.length;
  const out = new Uint8Array(n);
  for (let i = 0; i < n; i++) {
    const c = classes[i];
    if (c === 0) continue;
    if (rule.value !== undefined) {
      const v = values[i];
      out[i] = (end === "high" ? v >= rule.value : v <= rule.value) ? 1 : 0;
    } else if (rule.class_min !== undefined) {
      out[i] = c >= rule.class_min ? 1 : 0;
    } else if (rule.class_max !== undefined) {
      out[i] = c <= rule.class_max ? 1 : 0;
    }
  }
  return out;
}

/** Règle par défaut quand un indicateur n'en définit pas (composition libre). */
export function ruleFor(ind: Indicator, end: End): EndRule {
  return ind[end] ?? (end === "high" ? { class_min: 4 } : { class_max: 2 });
}

export interface Overlap {
  mask: Uint8Array;
  cells: number;
  hectares: number;
  share: number;
  residents: number | null;
  /** Hectares de chaque condition prise seule, pour lire le recouvrement. */
  aHectares: number;
  bHectares: number;
}

export function overlap(
  a: { side: PairSide; ind: Indicator; layer: Layer },
  b: { side: PairSide; ind: Indicator; layer: Layer },
  areasKm2: Float64Array,
  residents: Float32Array | null,
): Overlap {
  const ma = endMask(a.layer, ruleFor(a.ind, a.side.end), a.side.end);
  const mb = endMask(b.layer, ruleFor(b.ind, b.side.end), b.side.end);
  const n = ma.length;
  const mask = new Uint8Array(n);
  let cells = 0, km2 = 0, total = 0, aKm2 = 0, bKm2 = 0, res = 0;
  for (let i = 0; i < n; i++) {
    const s = areasKm2[i];
    total += s;
    if (ma[i]) aKm2 += s;
    if (mb[i]) bKm2 += s;
    if (ma[i] && mb[i]) {
      mask[i] = 1;
      cells++;
      km2 += s;
      if (residents) {
        const r = residents[i];
        if (Number.isFinite(r)) res += r;
      }
    }
  }
  return {
    mask,
    cells,
    hectares: km2 * 100,
    share: total ? km2 / total : 0,
    residents: residents ? res : null,
    aHectares: aKm2 * 100,
    bHectares: bKm2 * 100,
  };
}

export function describeEnd(ind: Indicator, end: End, fmt: (v: number) => string): string {
  const r = ruleFor(ind, end);
  if (r.value !== undefined) return `${end === "high" ? "≥" : "≤"} ${fmt(r.value)}`;
  if (r.class_min !== undefined) return `classes ${r.class_min} à 5`;
  if (r.class_max !== undefined) return `classes 1 à ${r.class_max}`;
  return "";
}
