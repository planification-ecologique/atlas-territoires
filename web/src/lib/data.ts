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

/** Tableau encodé par le pipeline : octets little-endian en base64 dans du JSON.
 * Les proxys d'administration (postes SPM) refusent les fichiers binaires. */
export interface PackedArray {
  dtype: string;
  length: number;
  base64: string;
}

const BYTES: Record<string, number> = { "<u8": 8, "<f4": 4, "<i4": 4, u1: 1 };

export function unpackBytes(p: PackedArray): ArrayBuffer {
  const bin = atob(p.base64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const size = BYTES[p.dtype];
  if (!size) throw new Error(`type de tableau inconnu : ${p.dtype}`);
  if (bytes.length !== p.length * size) throw new Error(`tableau tronqué (${bytes.length} octets)`);
  return bytes.buffer;
}

/** Cellules H3 sous forme de chaînes hexadécimales, dans l'ordre des fichiers. */
export async function loadCells(region: string, res: number): Promise<string[]> {
  const packed: PackedArray = await (await fetchOk(`${BASE}/${region}/r${res}/cells.json`)).json();
  const ints = new BigUint64Array(unpackBytes(packed));
  const out = new Array<string>(ints.length);
  for (let i = 0; i < ints.length; i++) out[i] = ints[i].toString(16);
  return out;
}

const layerCache = new Map<string, Promise<Layer>>();

export function loadLayer(region: string, res: number, id: string): Promise<Layer> {
  const key = `${region}/${res}/${id}`;
  let p = layerCache.get(key);
  if (!p) {
    p = fetchOk(`${BASE}/${region}/r${res}/${id}.json`)
      .then((r) => r.json() as Promise<{ values: PackedArray; classes: PackedArray }>)
      .then((d) => ({ values: new Float32Array(unpackBytes(d.values)), classes: new Uint8Array(unpackBytes(d.classes)) }));
    layerCache.set(key, p);
  }
  return p;
}
