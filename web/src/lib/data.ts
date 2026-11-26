import type { Layer, Manifest, RegionEntry, Registry } from "./types";

const BASE = `${import.meta.env.BASE_URL}data`;

async function fetchOk(url: string): Promise<Response> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} : HTTP ${r.status}`);
  return r;
}

export async function loadRegistry(): Promise<Registry> {
  return (await fetchOk(`${BASE}/registry.json`)).json();
}

/** Régions déjà construites (data/index.json). */
export async function loadIndex(): Promise<RegionEntry[]> {
  try {
    return await (await fetchOk(`${BASE}/index.json`)).json();
  } catch {
    return [];
  }
}

export async function loadManifest(region: string): Promise<Manifest> {
  return (await fetchOk(`${BASE}/${region}/manifest.json`)).json();
}

/** Cellules H3 sous forme de chaînes hexadécimales, dans l'ordre des fichiers. */
export async function loadCells(region: string, res: number): Promise<string[]> {
  const buf = await (await fetchOk(`${BASE}/${region}/r${res}/cells.u64`)).arrayBuffer();
  const ints = new BigUint64Array(buf);
  const out = new Array<string>(ints.length);
  for (let i = 0; i < ints.length; i++) out[i] = ints[i].toString(16);
  return out;
}

const layerCache = new Map<string, Promise<Layer>>();

export function loadLayer(region: string, res: number, id: string): Promise<Layer> {
  const key = `${region}/${res}/${id}`;
  let p = layerCache.get(key);
  if (!p) {
    p = Promise.all([
      fetchOk(`${BASE}/${region}/r${res}/${id}.f32`).then((r) => r.arrayBuffer()),
      fetchOk(`${BASE}/${region}/r${res}/${id}.c8`).then((r) => r.arrayBuffer()),
    ]).then(([v, c]) => ({ values: new Float32Array(v), classes: new Uint8Array(c) }));
    layerCache.set(key, p);
  }
  return p;
}
