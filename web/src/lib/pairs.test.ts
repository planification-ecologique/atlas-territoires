import { describe, expect, it } from "vitest";
import { endMask, overlap } from "./pairs";
import type { Indicator, Layer } from "./types";

const ind = (id: string, extra: Partial<Indicator> = {}): Indicator => ({
  id,
  label: id,
  theme: "t",
  role: "etat",
  unit: "u",
  classes: "seuils",
  description: "",
  source: { id: "s", label: "s" },
  ...extra,
});

const layer = (values: number[], classes: number[]): Layer => ({
  values: Float32Array.from(values),
  classes: Uint8Array.from(classes),
});

describe("endMask", () => {
  it("applique un seuil de valeur et ignore les cellules sans donnée", () => {
    const l = layer([0.1, 0.5, 0.9, NaN], [1, 3, 5, 0]);
    expect(Array.from(endMask(l, { value: 0.5 }, "high"))).toEqual([0, 1, 1, 0]);
    expect(Array.from(endMask(l, { value: 0.5 }, "low"))).toEqual([1, 1, 0, 0]);
  });

  it("applique un seuil de classe", () => {
    const l = layer([1, 2, 3, 4], [1, 2, 4, 5]);
    expect(Array.from(endMask(l, { class_min: 4 }, "high"))).toEqual([0, 0, 1, 1]);
    expect(Array.from(endMask(l, { class_max: 2 }, "low"))).toEqual([1, 1, 0, 0]);
  });
});

describe("overlap", () => {
  it("compte surfaces et habitants du recouvrement", () => {
    const a = { side: { indicator: "a", end: "high" as const }, ind: ind("a", { high: { value: 1 } }), layer: layer([0, 1, 2, 3], [1, 2, 3, 4]) };
    const b = { side: { indicator: "b", end: "low" as const }, ind: ind("b", { low: { value: 5 } }), layer: layer([9, 1, 9, 1], [5, 1, 5, 1]) };
    const areas = Float64Array.from([1, 1, 1, 1]);
    const residents = Float32Array.from([10, 20, 30, 40]);
    const o = overlap(a, b, areas, residents);
    expect(Array.from(o.mask)).toEqual([0, 1, 0, 1]);
    expect(o.hectares).toBe(200);
    expect(o.share).toBe(0.5);
    expect(o.residents).toBe(60);
    expect(o.aHectares).toBe(300);
    expect(o.bHectares).toBe(200);
  });
});
