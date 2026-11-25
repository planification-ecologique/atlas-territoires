import { useEffect, useRef } from "react";
import maplibregl, { type ExpressionSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { cellToBoundary } from "h3-js";
import type { RegionInfo } from "../lib/types";

/** Ce que la carte affiche : un état 0..5 par hexagone et la palette associée. */
export interface MapView {
  state: Uint8Array;
  /** couleurs des états 1..n (l'état 0 est transparent) */
  colors: string[];
  key: string;
}

interface Props {
  cells: string[];
  region: RegionInfo;
  view: MapView | null;
  flyTo: { lng: number; lat: number; t: number } | null;
  onHover: (index: number | null, point: { x: number; y: number } | null) => void;
}

const SRC = "hex";

// Fond Plan IGN, style vectoriel gris officiel de la Géoplateforme.
const BASEMAP = "https://data.geopf.fr/annexes/ressources/vectorTiles/styles/PLAN.IGN/gris.json";

function fillColor(colors: string[]): ExpressionSpecification {
  const match: unknown[] = ["match", ["coalesce", ["feature-state", "s"], 0]];
  colors.forEach((c, i) => match.push(i + 1, c));
  match.push("rgba(0,0,0,0)");
  return match as ExpressionSpecification;
}

export function HexMap({ cells, region, view, flyTo, onHover }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const ready = useRef(false);
  const applied = useRef<Uint8Array | null>(null);
  const pending = useRef<MapView | null>(null);
  const hoverCb = useRef(onHover);
  hoverCb.current = onHover;

  const apply = (v: MapView) => {
    const map = mapRef.current;
    if (!map || !ready.current) {
      pending.current = v;
      return;
    }
    const prev = applied.current;
    for (let i = 0; i < v.state.length; i++) {
      if (!prev || prev[i] !== v.state[i]) map.setFeatureState({ source: SRC, id: i }, { s: v.state[i] });
    }
    applied.current = v.state.slice();
    map.setPaintProperty("hex-fill", "fill-color", fillColor(v.colors));
  };

  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: BASEMAP,
      bounds: region.bbox,
      fitBoundsOptions: { padding: 24 },
      attributionControl: { compact: true, customAttribution: "© IGN – Plan IGN" },
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");

    // Si le fond IGN ne répond pas, on garde la grille sur un fond uni.
    const fallback = setTimeout(() => {
      if (!ready.current) map.setStyle({ version: 8, sources: {}, layers: [{ id: "fond", type: "background", paint: { "background-color": "#f2f2f0" } }] });
    }, 8000);
    map.on("error", (e) => {
      if (!ready.current && !map.isStyleLoaded() && String(e.error?.message ?? "").includes("gris.json")) {
        clearTimeout(fallback);
        map.setStyle({ version: 8, sources: {}, layers: [{ id: "fond", type: "background", paint: { "background-color": "#f2f2f0" } }] });
      }
    });

    map.on("load", () => {
      clearTimeout(fallback);
      const features = cells.map((h, i) => ({
        type: "Feature" as const,
        id: i,
        properties: {},
        geometry: { type: "Polygon" as const, coordinates: [cellToBoundary(h, true)] },
      }));
      map.addSource(SRC, { type: "geojson", data: { type: "FeatureCollection", features } });
      // Les hexagones passent sous les libellés du fond pour garder les noms lisibles.
      const beforeId = map.getStyle().layers.find((l) => l.type === "symbol")?.id;
      map.addLayer({
        id: "hex-fill",
        type: "fill",
        source: SRC,
        paint: { "fill-color": "rgba(0,0,0,0)", "fill-opacity": 0.78, "fill-antialias": false },
      }, beforeId);
      map.addLayer({
        id: "hex-line",
        type: "line",
        source: SRC,
        minzoom: 10,
        paint: { "line-color": "rgba(40,40,40,0.25)", "line-width": 0.5 },
      }, beforeId);
      ready.current = true;
      if (pending.current) apply(pending.current);
    });

    map.on("mousemove", "hex-fill", (e) => {
      const f = e.features?.[0];
      map.getCanvas().style.cursor = f ? "crosshair" : "";
      hoverCb.current(f ? Number(f.id) : null, { x: e.point.x, y: e.point.y });
    });
    map.on("mouseleave", "hex-fill", () => {
      map.getCanvas().style.cursor = "";
      hoverCb.current(null, null);
    });

    return () => {
      clearTimeout(fallback);
      ready.current = false;
      applied.current = null;
      map.remove();
    };
    // La grille ne change qu'avec la région.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cells]);

  useEffect(() => {
    if (view) apply(view);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view?.key]);

  useEffect(() => {
    if (flyTo && mapRef.current) mapRef.current.flyTo({ center: [flyTo.lng, flyTo.lat], zoom: 11 });
  }, [flyTo]);

  // Pour les tests et le débogage.
  useEffect(() => {
    (window as unknown as { __map?: maplibregl.Map | null }).__map = mapRef.current;
  });

  return <div ref={container} className="map" />;
}
