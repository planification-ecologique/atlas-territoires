import type { Indicator, Role } from "./types";

const nf0 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });
const nf2 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 });
const pct = new Intl.NumberFormat("fr-FR", { style: "percent", maximumFractionDigits: 0 });
const pct1 = new Intl.NumberFormat("fr-FR", { style: "percent", maximumFractionDigits: 1 });

export const isShare = (ind: Indicator) => ind.unit.startsWith("part");

export function fmtValue(ind: Indicator, v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "n.d.";
  if (isShare(ind)) return pct.format(v);
  const unit = ind.unit;
  if (Math.abs(v) >= 100) return `${nf0.format(v)} ${unit}`;
  if (Math.abs(v) >= 1) return `${nf1.format(v)} ${unit}`;
  return `${nf2.format(v)} ${unit}`;
}

export const fmtInt = (v: number) => nf0.format(v);
export const fmtPct = (v: number) => pct1.format(v);
export const fmtHa = (ha: number) => (ha >= 10000 ? `${nf1.format(ha / 100)} km²` : `${nf0.format(ha)} ha`);

/** Palettes séquentielles à 5 classes, une par rôle. */
export const PALETTES: Record<Role, string[]> = {
  etat: ["#eef3fb", "#bcd0ec", "#7ea7d8", "#3f74b8", "#1c437f"],
  risque: ["#fdf0e4", "#f9c99a", "#f19a55", "#d8632a", "#9c3511"],
  contrainte: ["#eef7ec", "#bfe2b4", "#7fc36f", "#3c9645", "#16602a"],
  opportunite: ["#f4effa", "#d4c4ea", "#a98bd3", "#7a56b3", "#4b2c82"],
};

export const PAIR_COLORS = { conflit: "#c8362b", synergie: "#1f8a5a" } as const;

export const ROLE_LABELS: Record<Role, string> = {
  etat: "État du territoire",
  risque: "Risque",
  contrainte: "Protection",
  opportunite: "Potentiel",
};
