// The small map in the detail panel: one scene, its outline and its image tiles.
import L from "leaflet";
import { API, authHeaders } from "../api";
import type { Feature } from "../api";

// A tile layer that can send the user's token (plain <img> tags cannot).
class AuthTileLayer extends L.TileLayer {
  constructor(url: string, private token: string | undefined, options?: L.TileLayerOptions) {
    super(url, options);
  }
  createTile(coords: L.Coords, done: L.DoneCallback): HTMLElement {
    const img = document.createElement("img");
    fetch(this.getTileUrl(coords), { headers: authHeaders(this.token) })
      .then((r) => (r.ok ? r.blob() : Promise.reject(r.status)))
      .then((b) => {
        img.src = URL.createObjectURL(b);
        done(undefined, img);
      })
      .catch((e) => done(new Error(String(e)), img));
    return img;
  }
}

export function showDetail(map: L.Map, group: L.LayerGroup, feature: Feature, token?: string) {
  group.clearLayers();
  const outline = L.geoJSON(feature as any, { style: { color: "#e65100", weight: 2, fillOpacity: 0.05 } }).addTo(group);
  new AuthTileLayer(`${API}/tiles/${feature.id}/{z}/{x}/{y}.png`, token, { minZoom: 3, maxZoom: 14, opacity: 0.8 }).addTo(group);
  map.fitBounds(outline.getBounds(), { padding: [10, 10], maxZoom: 9 });
}
