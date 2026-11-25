export type Role = "etat" | "risque" | "opportunite" | "contrainte";
export type End = "high" | "low";

export interface EndRule {
  value?: number;
  class_min?: number;
  class_max?: number;
}

export interface Indicator {
  id: string;
  label: string;
  theme: string;
  role: Role;
  unit: string;
  classes: "quantiles" | "seuils";
  breaks?: number[];
  high?: EndRule;
  low?: EndRule;
  weight?: boolean;
  description: string;
  source: { id: string; label: string; licence?: string; page?: string };
}

export interface PairSide {
  indicator: string;
  end: End;
}

export interface Pair {
  id: string;
  type: "conflit" | "synergie";
  a: PairSide;
  b: PairSide;
  title: string;
  question: string;
}

export interface RegionInfo {
  name: string;
  bbox: [number, number, number, number];
  center: [number, number];
  zoom: number;
}

export interface Registry {
  themes: Record<string, string>;
  indicators: Indicator[];
  pairs: Pair[];
  regions: Record<string, RegionInfo>;
}

export interface IndicatorMeta {
  breaks: number[];
  coverage: number;
  min: number | null;
  max: number | null;
  mean: number | null;
}

export interface PairStats {
  cells: number;
  hectares: number;
  share: number;
  residents?: number;
}

export interface Manifest {
  region: string;
  name: string;
  res: number;
  cells: number;
  area_km2: number;
  synthetic: boolean;
  built: string;
  indicators: Record<string, IndicatorMeta>;
  pairs: Record<string, PairStats>;
  places: { name: string; lng: number; lat: number }[];
}

/** Une couche chargée : valeurs et classes alignées sur la liste des cellules. */
export interface Layer {
  values: Float32Array;
  classes: Uint8Array;
}
