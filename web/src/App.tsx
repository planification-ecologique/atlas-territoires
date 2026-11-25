import { useCallback, useEffect, useMemo, useState } from "react";
import { cellArea } from "h3-js";
import { HexMap, type MapView } from "./components/HexMap";
import { loadCells, loadLayer, loadManifest, loadRegistry } from "./lib/data";
import { describeEnd, endMask, overlap, ruleFor, type Overlap } from "./lib/pairs";
import { fmtHa, fmtInt, fmtPct, fmtValue, PAIR_COLORS, PALETTES, ROLE_LABELS } from "./lib/format";
import type { End, Indicator, Layer, Manifest, Pair, Registry } from "./lib/types";

const REGION = new URLSearchParams(location.search).get("region") ?? "24";

type Tab = "paires" | "indicateurs" | "composer";

interface Loaded {
  registry: Registry;
  manifest: Manifest;
  cells: string[];
  areas: Float64Array;
  layers: Record<string, Layer>;
}

export default function App() {
  const [data, setData] = useState<Loaded | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("paires");
  const [indicatorId, setIndicatorId] = useState<string>("conso_enaf");
  const [pairId, setPairId] = useState<string | null>(null);
  const [custom, setCustom] = useState<Pair>({
    id: "libre",
    type: "conflit",
    a: { indicator: "pop_densite", end: "high" },
    b: { indicator: "inondation_eaip", end: "high" },
    title: "Paire composée",
    question: "",
  });
  const [hover, setHover] = useState<{ i: number; x: number; y: number } | null>(null);
  const [flyTo, setFlyTo] = useState<{ lng: number; lat: number; t: number } | null>(null);

  useEffect(() => {
    (async () => {
      const registry = await loadRegistry();
      const manifest = await loadManifest(REGION);
      const cells = await loadCells(REGION, manifest.res);
      const areas = Float64Array.from(cells, (c) => cellArea(c, "km2"));
      const ids = registry.indicators.map((i) => i.id).filter((id) => id in manifest.indicators);
      const loaded = await Promise.all(ids.map((id) => loadLayer(REGION, manifest.res, id)));
      const layers = Object.fromEntries(ids.map((id, k) => [id, loaded[k]]));
      setData({ registry, manifest, cells, areas, layers });
      const first = registry.pairs.find((p) => p.id in manifest.pairs);
      setPairId(first?.id ?? null);
    })().catch((e) => setError(String(e)));
  }, []);

  const indicators = useMemo(
    () => Object.fromEntries((data?.registry.indicators ?? []).map((i) => [i.id, i])) as Record<string, Indicator>,
    [data],
  );
  const available = useMemo(
    () => (data ? data.registry.indicators.filter((i) => data.layers[i.id]) : []),
    [data],
  );
  const residents = useMemo(() => {
    const w = data?.registry.indicators.find((i) => i.weight);
    return w && data?.layers[w.id] ? data.layers[w.id].values : null;
  }, [data]);

  const activePair: Pair | null = useMemo(() => {
    if (!data) return null;
    if (tab === "composer") return custom;
    if (tab === "paires") return data.registry.pairs.find((p) => p.id === pairId) ?? null;
    return null;
  }, [data, tab, pairId, custom]);

  const ov: Overlap | null = useMemo(() => {
    if (!data || !activePair) return null;
    const la = data.layers[activePair.a.indicator];
    const lb = data.layers[activePair.b.indicator];
    if (!la || !lb) return null;
    return overlap(
      { side: activePair.a, ind: indicators[activePair.a.indicator], layer: la },
      { side: activePair.b, ind: indicators[activePair.b.indicator], layer: lb },
      data.areas,
      residents,
    );
  }, [data, activePair, indicators, residents]);

  const view: MapView | null = useMemo(() => {
    if (!data) return null;
    if (activePair && ov) {
      // états : 1 = condition A seule, 2 = condition B seule, 3 = les deux
      const { mask } = ov;
      const la = data.layers[activePair.a.indicator];
      const lb = data.layers[activePair.b.indicator];
      const ia = indicators[activePair.a.indicator];
      const ib = indicators[activePair.b.indicator];
      const ma = endMaskCached(la, ia, activePair.a.end);
      const mb = endMaskCached(lb, ib, activePair.b.end);
      const state = new Uint8Array(mask.length);
      for (let i = 0; i < mask.length; i++) state[i] = mask[i] ? 3 : ma[i] ? 1 : mb[i] ? 2 : 0;
      return {
        state,
        colors: ["#c9c3b4", "#a9b9c9", activePair.type === "conflit" ? PAIR_COLORS.conflit : PAIR_COLORS.synergie],
        key: `pair:${activePair.id}:${activePair.a.indicator}:${activePair.a.end}:${activePair.b.indicator}:${activePair.b.end}:${activePair.type}`,
      };
    }
    const layer = data.layers[indicatorId];
    if (!layer) return null;
    return { state: layer.classes, colors: PALETTES[indicators[indicatorId].role], key: `ind:${indicatorId}` };
  }, [data, activePair, ov, indicatorId, indicators]);

  const onHover = useCallback((i: number | null, p: { x: number; y: number } | null) => {
    setHover(i === null || !p ? null : { i, ...p });
  }, []);

  if (error) return <div className="splash">Impossible de charger les données : {error}</div>;
  if (!data) return <div className="splash">Chargement de la grille…</div>;

  const { registry, manifest } = data;
  const region = registry.regions[REGION];

  return (
    <div className="app">
      <aside className="panel">
        <header>
          <p className="eyebrow">Atlas des territoires · prototype</p>
          <h1>{manifest.name}</h1>
          <p className="muted">
            {fmtInt(manifest.cells)} hexagones H3 (résolution {manifest.res}, ≈ 74 ha) · {fmtInt(manifest.area_km2)} km²
          </p>
          {manifest.synthetic && (
            <p className="banner" role="note">
              Données de démonstration synthétiques : les motifs imitent la géographie régionale mais aucune valeur
              n'est réelle. Lancer <code>python -m atlas_pipeline build</code> pour les sources ouvertes.
            </p>
          )}
          <Search places={manifest.places} onPick={(p) => setFlyTo({ ...p, t: Date.now() })} />
        </header>

        <nav className="tabs" role="tablist">
          {(
            [
              ["paires", "Conflits et synergies"],
              ["composer", "Composer"],
              ["indicateurs", "Indicateurs"],
            ] as [Tab, string][]
          ).map(([t, label]) => (
            <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>
              {label}
            </button>
          ))}
        </nav>

        <div className="scroll">
          {tab === "paires" && (
            <PairList
              pairs={registry.pairs.filter((p) => p.a.indicator in data.layers && p.b.indicator in data.layers)}
              stats={manifest.pairs}
              selected={pairId}
              onSelect={setPairId}
              indicators={indicators}
              ov={ov}
            />
          )}
          {tab === "composer" && (
            <Composer pair={custom} onChange={setCustom} indicators={available} byId={indicators} ov={ov} />
          )}
          {tab === "indicateurs" && (
            <IndicatorList
              registry={registry}
              available={available}
              manifest={manifest}
              selected={indicatorId}
              onSelect={setIndicatorId}
            />
          )}
        </div>
        <footer className="muted small">
          {available.length} indicateurs, {registry.pairs.length} paires. Sources et licences dans l'onglet Indicateurs.
          Grille <a href="https://h3geo.org" target="_blank" rel="noreferrer">H3</a>, fond © IGN.
        </footer>
      </aside>

      <main className="mapwrap">
        <HexMap cells={data.cells} region={region} view={view} flyTo={flyTo} onHover={onHover} />
        {activePair && ov ? <PairLegend pair={activePair} indicators={indicators} /> : <IndicatorLegend ind={indicators[indicatorId]} meta={manifest.indicators[indicatorId]} />}
        {hover && (
          <Tooltip
            x={hover.x}
            y={hover.y}
            i={hover.i}
            layers={data.layers}
            indicators={available}
            highlight={activePair ? [activePair.a.indicator, activePair.b.indicator] : [indicatorId]}
          />
        )}
      </main>
    </div>
  );
}

// --- Masques mis en cache pour la vue carte --------------------------------

const maskCache = new WeakMap<Layer, Map<string, Uint8Array>>();
function endMaskCached(layer: Layer, ind: Indicator, end: End): Uint8Array {
  let m = maskCache.get(layer);
  if (!m) maskCache.set(layer, (m = new Map()));
  const k = `${ind.id}:${end}`;
  let v = m.get(k);
  if (!v) m.set(k, (v = endMask(layer, ruleFor(ind, end), end)));
  return v;
}

// --- Composants -------------------------------------------------------------

function endLabel(ind: Indicator, end: End) {
  return `${ind.label} ${end === "high" ? "élevé(e)" : "faible"} (${describeEnd(ind, end, (v) => fmtValue(ind, v))})`;
}

function PairList(props: {
  pairs: Pair[];
  stats: Manifest["pairs"];
  selected: string | null;
  onSelect: (id: string) => void;
  indicators: Record<string, Indicator>;
  ov: Overlap | null;
}) {
  const { pairs, stats, selected, onSelect, indicators, ov } = props;
  const sorted = [...pairs].sort((a, b) => (stats[b.id]?.hectares ?? 0) - (stats[a.id]?.hectares ?? 0));
  const maxHa = Math.max(1, ...sorted.map((p) => stats[p.id]?.hectares ?? 0));
  return (
    <ul className="pairs">
      {sorted.map((p) => {
        const s = stats[p.id];
        const on = p.id === selected;
        return (
          <li key={p.id} className={`pair ${p.type} ${on ? "on" : ""}`}>
            <button onClick={() => onSelect(p.id)} aria-expanded={on}>
              <span className={`badge ${p.type}`}>{p.type === "conflit" ? "Conflit" : "Synergie"}</span>
              <span className="title">{p.title}</span>
              {s && (
                <span className="bar" aria-hidden>
                  <span style={{ width: `${(100 * s.hectares) / maxHa}%` }} />
                </span>
              )}
              {s && (
                <span className="nums">
                  {fmtHa(s.hectares)} · {fmtPct(s.share)} de la région
                  {s.residents !== undefined && ` · ${fmtInt(s.residents)} hab.`}
                </span>
              )}
            </button>
            {on && (
              <div className="detail">
                <p className="question">{p.question}</p>
                <ul className="conds">
                  <li><span className="sw a" /> {endLabel(indicators[p.a.indicator], p.a.end)}</li>
                  <li><span className="sw b" /> {endLabel(indicators[p.b.indicator], p.b.end)}</li>
                </ul>
                {ov && <OverlapFigures ov={ov} />}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function OverlapFigures({ ov }: { ov: Overlap }) {
  const ofA = ov.aHectares ? ov.hectares / ov.aHectares : 0;
  const ofB = ov.bHectares ? ov.hectares / ov.bHectares : 0;
  return (
    <dl className="figures">
      <div><dt>Recouvrement</dt><dd>{fmtHa(ov.hectares)}</dd></div>
      {ov.residents !== null && <div><dt>Habitants concernés</dt><dd>{fmtInt(ov.residents)}</dd></div>}
      <div><dt>Part de la condition A</dt><dd>{fmtPct(ofA)}</dd></div>
      <div><dt>Part de la condition B</dt><dd>{fmtPct(ofB)}</dd></div>
    </dl>
  );
}

function Composer(props: {
  pair: Pair;
  onChange: (p: Pair) => void;
  indicators: Indicator[];
  byId: Record<string, Indicator>;
  ov: Overlap | null;
}) {
  const { pair, onChange, indicators, byId, ov } = props;
  const side = (k: "a" | "b") => (
    <fieldset className="side">
      <legend>Condition {k.toUpperCase()}</legend>
      <select
        value={pair[k].indicator}
        onChange={(e) => onChange({ ...pair, [k]: { ...pair[k], indicator: e.target.value } })}
      >
        {indicators.map((i) => (
          <option key={i.id} value={i.id}>{i.label}</option>
        ))}
      </select>
      <div className="seg">
        {(["high", "low"] as End[]).map((e) => (
          <button key={e} className={pair[k].end === e ? "on" : ""} onClick={() => onChange({ ...pair, [k]: { ...pair[k], end: e } })}>
            {e === "high" ? "Élevé" : "Faible"}
          </button>
        ))}
      </div>
      <p className="muted small">{describeEnd(byId[pair[k].indicator], pair[k].end, (v) => fmtValue(byId[pair[k].indicator], v))}</p>
    </fieldset>
  );
  return (
    <div className="composer">
      <p className="muted">
        Croisez deux indicateurs pour faire apparaître une tension ou une complémentarité qui n'est pas encore dans la
        liste. Une paire utile peut ensuite être ajoutée à <code>registry/pairs.yaml</code>.
      </p>
      {side("a")}
      {side("b")}
      <div className="seg type">
        {(["conflit", "synergie"] as const).map((t) => (
          <button key={t} className={pair.type === t ? `on ${t}` : ""} onClick={() => onChange({ ...pair, type: t })}>
            {t === "conflit" ? "Conflit" : "Synergie"}
          </button>
        ))}
      </div>
      {ov && <OverlapFigures ov={ov} />}
    </div>
  );
}

function IndicatorList(props: {
  registry: Registry;
  available: Indicator[];
  manifest: Manifest;
  selected: string;
  onSelect: (id: string) => void;
}) {
  const { registry, available, manifest, selected, onSelect } = props;
  return (
    <div className="indicators">
      {Object.entries(registry.themes).map(([theme, label]) => {
        const items = available.filter((i) => i.theme === theme);
        if (!items.length) return null;
        return (
          <section key={theme}>
            <h2>{label}</h2>
            <ul>
              {items.map((i) => (
                <li key={i.id} className={i.id === selected ? "on" : ""}>
                  <button onClick={() => onSelect(i.id)}>
                    <span className="swatch" style={{ background: PALETTES[i.role][3] }} />
                    {i.label}
                    <span className="muted small"> · {ROLE_LABELS[i.role]}</span>
                  </button>
                  {i.id === selected && (
                    <div className="detail">
                      <p>{i.description}</p>
                      <p className="muted small">
                        Moyenne {fmtValue(i, manifest.indicators[i.id]?.mean)} · couverture{" "}
                        {fmtPct(manifest.indicators[i.id]?.coverage ?? 0)} des hexagones
                        <br />
                        Source :{" "}
                        {i.source.page ? <a href={i.source.page} target="_blank" rel="noreferrer">{i.source.label}</a> : i.source.label}
                        {i.source.licence && ` (${i.source.licence})`}
                      </p>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

function IndicatorLegend({ ind, meta }: { ind?: Indicator; meta?: Manifest["indicators"][string] }) {
  if (!ind || !meta) return null;
  const b = meta.breaks;
  const labels = [`≤ ${fmtValue(ind, b[0])}`, ...b.slice(0, 3).map((x, k) => `${fmtValue(ind, x)} – ${fmtValue(ind, b[k + 1])}`), `> ${fmtValue(ind, b[3])}`];
  return (
    <div className="legend">
      <strong>{ind.label}</strong>
      <ul>
        {PALETTES[ind.role].map((c, k) => (
          <li key={c}><span className="sw" style={{ background: c }} />{labels[k]}</li>
        ))}
      </ul>
    </div>
  );
}

function PairLegend({ pair, indicators }: { pair: Pair; indicators: Record<string, Indicator> }) {
  return (
    <div className="legend">
      <strong>{pair.title}</strong>
      <ul>
        <li><span className="sw" style={{ background: pair.type === "conflit" ? PAIR_COLORS.conflit : PAIR_COLORS.synergie }} />Les deux conditions</li>
        <li><span className="sw" style={{ background: "#c9c3b4" }} />A seule : {indicators[pair.a.indicator].label} {pair.a.end === "high" ? "élevé(e)" : "faible"}</li>
        <li><span className="sw" style={{ background: "#a9b9c9" }} />B seule : {indicators[pair.b.indicator].label} {pair.b.end === "high" ? "élevé(e)" : "faible"}</li>
      </ul>
    </div>
  );
}

function Tooltip(props: { x: number; y: number; i: number; layers: Record<string, Layer>; indicators: Indicator[]; highlight: string[] }) {
  const { x, y, i, layers, indicators, highlight } = props;
  return (
    <div className="tooltip" style={{ left: x + 14, top: y + 14 }}>
      <table>
        <tbody>
          {indicators.map((ind) => (
            <tr key={ind.id} className={highlight.includes(ind.id) ? "hl" : ""}>
              <th>{ind.label}</th>
              <td>{fmtValue(ind, layers[ind.id].values[i])}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Search({ places, onPick }: { places: Manifest["places"]; onPick: (p: { lng: number; lat: number }) => void }) {
  const [q, setQ] = useState("");
  const norm = (s: string) => s.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();
  const hits = q.length < 2 ? [] : places.filter((p) => norm(p.name).startsWith(norm(q))).slice(0, 6);
  return (
    <div className="search">
      <input
        type="search"
        placeholder="Aller à une commune…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && hits[0]) {
            onPick(hits[0]);
            setQ("");
          }
        }}
        aria-label="Rechercher une commune"
      />
      {hits.length > 0 && (
        <ul>
          {hits.map((p) => (
            <li key={p.name}>
              <button onClick={() => { onPick(p); setQ(""); }}>{p.name}</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
