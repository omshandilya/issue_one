// Lets the user draw any polygon: click points, double-click to finish.
import L from "leaflet";

export type GeoJSONPolygon = {
  type: "Polygon";
  coordinates: number[][][];
};

export function enablePolygonDrawing(map: L.Map, onPolygon: (poly: GeoJSONPolygon) => void): () => void {
  const points: L.LatLng[] = [];
  let polyline: L.Polyline | null = null;
  let polygonPreview: L.Polygon | null = null;
  map.doubleClickZoom.disable();
  map.getContainer().style.cursor = "crosshair";

  const updatePreview = (cursor?: L.LatLng) => {
    const pts = cursor ? [...points, cursor] : points;
    if (pts.length > 2) {
      if (!polygonPreview) {
        polygonPreview = L.polygon(pts, { color: "#2e7d32", weight: 2, fillOpacity: 0.15 }).addTo(map);
      } else {
        polygonPreview.setLatLngs(pts);
      }
    }
    if (pts.length > 1) {
      if (!polyline) {
        polyline = L.polyline(pts, { color: "#2e7d32", weight: 2, dashArray: "4" }).addTo(map);
      } else {
        polyline.setLatLngs(pts);
      }
    }
  };

  const onClick = (e: L.LeafletMouseEvent) => {
    // Avoid immediate duplicate points
    if (points.length > 0) {
      const last = points[points.length - 1];
      if (last.lat === e.latlng.lat && last.lng === e.latlng.lng) return;
    }
    points.push(e.latlng);
    updatePreview();
  };

  const onMouseMove = (e: L.LeafletMouseEvent) => {
    if (points.length > 0) {
      updatePreview(e.latlng);
    }
  };

  const onDblClick = (e: L.LeafletMouseEvent) => {
    L.DomEvent.stop(e);
    // Deduplicate consecutive points (double click often emits 2 close click events)
    const deduped: L.LatLng[] = [];
    for (const p of points) {
      if (deduped.length === 0) {
        deduped.push(p);
      } else {
        const last = deduped[deduped.length - 1];
        if (Math.abs(last.lat - p.lat) > 1e-5 || Math.abs(last.lng - p.lng) > 1e-5) {
          deduped.push(p);
        }
      }
    }
    if (deduped.length < 3) {
      stop();
      return;
    }
    // Convert points to [lon, lat] GeoJSON format and close ring
    const coords: number[][] = deduped.map((p) => [Number(p.lng.toFixed(5)), Number(p.lat.toFixed(5))]);
    coords.push([...coords[0]]);

    stop();
    onPolygon({
      type: "Polygon",
      coordinates: [coords],
    });
  };

  const stop = () => {
    map.off("click", onClick).off("mousemove", onMouseMove).off("dblclick", onDblClick);
    map.doubleClickZoom.enable();
    map.getContainer().style.cursor = "";
    if (polyline) {
      map.removeLayer(polyline);
      polyline = null;
    }
    if (polygonPreview) {
      map.removeLayer(polygonPreview);
      polygonPreview = null;
    }
  };

  map.on("click", onClick).on("mousemove", onMouseMove).on("dblclick", onDblClick);
  return stop;
}

