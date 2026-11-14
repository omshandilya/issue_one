// Talks to the portal gateway.
export const API =
  typeof window !== "undefined" && window.location.port !== "5173"
    ? window.location.origin
    : "http://127.0.0.1:8000";

export type Feature = {
  type: "Feature";
  id: string;
  geometry: { type: "Polygon" | "MultiPolygon"; coordinates: number[][][] | number[][][][] };
  properties: { id: string; name: string; datetime: string; access: string; has_file: boolean; size_bytes: number | null };
};

export type SearchResult = { numberMatched: number; numberReturned: number; features: Feature[] };

export const USERS: Record<string, string | undefined> = {
  "anonymous": undefined,
  "analyst_a (Unit A)": "tok-analyst-a-7f3c",
  "analyst_b (Unit B)": "tok-analyst-b-91d2",
};

export function authHeaders(token?: string): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// bbox is [min_lon, min_lat, max_lon, max_lat]
export async function search(bbox: number[], token?: string): Promise<SearchResult> {
  const r = await fetch(`${API}/search?bbox=${bbox.join(",")}&limit=200`, { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`search failed: ${r.status}`);
  return r.json();
}

export type PolygonSearchResult = SearchResult & { search_id: string };

export async function searchPolygon(polygon: { type: "Polygon"; coordinates: number[][][] }, token?: string): Promise<PolygonSearchResult> {
  const r = await fetch(`${API}/search/polygon?limit=200`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify(polygon),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || `polygon search failed: ${r.status}`);
  }
  return r.json();
}

export async function downloadExport(searchId: string, format: "geojson" | "csv", token?: string) {
  const r = await fetch(`${API}/export/${searchId}?format=${format}`, {
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`Export failed: ${r.status}`);
  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `export-${searchId}.${format}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
