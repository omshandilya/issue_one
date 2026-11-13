// Draws search results on the main map.
import L from "leaflet";
import type { Feature } from "../api";

const STYLE: L.PathOptions = { color: "#1565c0", weight: 2, fillOpacity: 0.12 };
const PICKED: L.PathOptions = { color: "#e65100", weight: 3, fillOpacity: 0.25 };

// A scene footprint is one polygon, or several when it crosses the date line.
function rings(f: Feature): number[][][] {
  const c = f.geometry.coordinates as any;
  return f.geometry.type === "Polygon" ? [c[0]] : c.map((poly: number[][][]) => poly[0]);
}

export function showResults(group: L.LayerGroup, features: Feature[], onPick: (id: string) => void) {
  group.clearLayers();
  const bounds = L.latLngBounds([]);
  for (const f of features) {
    for (const ring of rings(f)) {
      const poly = L.polygon(ring as L.LatLngExpression[], STYLE);
      poly.on("click", () => onPick(f.id));
      poly.bindTooltip(f.properties.name);
      poly.addTo(group);
      bounds.extend(poly.getBounds());
    }
  }
  return bounds;
}

// Highlights the scene the user picked in the list.
export function highlight(group: L.LayerGroup, features: Feature[], id: string | null) {
  group.eachLayer((layer) => {
    (layer as L.Polygon).setStyle(STYLE);
  });
  if (!id) return;
  const f = features.find((x) => x.id === id);
  if (!f) return;
  for (const ring of rings(f)) {
    L.geoJSON({ type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [ring] } } as any, { style: PICKED }).addTo(group);
  }
}
