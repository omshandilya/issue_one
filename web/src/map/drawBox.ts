// Lets the user draw a search box: press the button, then drag on the map.
import L from "leaflet";

// Returns [min_lon, min_lat, max_lon, max_lat]
export function enableBoxDrawing(map: L.Map, onBox: (bbox: number[]) => void): () => void {
  let start: L.LatLng | null = null;
  let rect: L.Rectangle | null = null;
  map.dragging.disable();
  map.getContainer().style.cursor = "crosshair";

  const down = (e: L.LeafletMouseEvent) => {
    start = e.latlng;
    rect = L.rectangle(L.latLngBounds(start, start), { color: "#2e7d32", weight: 2, dashArray: "4" }).addTo(map);
  };
  const move = (e: L.LeafletMouseEvent) => {
    if (start && rect) rect.setBounds(L.latLngBounds(start, e.latlng));
  };
  const up = (e: L.LeafletMouseEvent) => {
    if (!start || !rect) return;
    const end = e.latlng;
    const south = Math.min(start.lat, end.lat);
    const north = Math.max(start.lat, end.lat);
    let west = Math.min(start.lng, end.lng);
    let east = Math.max(start.lng, end.lng);
    if (Math.abs(start.lng - end.lng) > 180) {
      if (start.lng < end.lng) {
        west = end.lng;
        east = start.lng;
      } else {
        west = start.lng;
        east = end.lng;
      }
    }
    start = null;
    onBox([west, south, east, north]);
    stop();
  };
  const stop = () => {
    map.off("mousedown", down).off("mousemove", move).off("mouseup", up);
    map.dragging.enable();
    map.getContainer().style.cursor = "";
    if (rect) { map.removeLayer(rect); rect = null; }
  };
  map.on("mousedown", down).on("mousemove", move).on("mouseup", up);
  return stop;
}
