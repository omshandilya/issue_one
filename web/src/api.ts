// Talks to the portal gateway.
export const API = "http://127.0.0.1:8000";

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
