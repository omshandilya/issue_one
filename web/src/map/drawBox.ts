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
    const b = L.latLngBounds(start, e.latlng);
    start = null;
    onBox([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]);
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
