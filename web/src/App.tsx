import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import { search, USERS } from "./api";
import type { Feature } from "./api";
import { showResults, highlight } from "./map/resultsLayer";
import { showDetail } from "./map/detailMap";
import { enableBoxDrawing } from "./map/drawBox";

const AREAS: Record<string, number[]> = {
  "Mumbai port": [72.7, 18.8, 73.0, 19.1],
  "Gulf of Kutch": [69.0, 22.0, 70.5, 23.5],
  "Odisha coast": [84.5, 19.0, 87.5, 21.8],
};

export default function App() {
  const mainEl = useRef<HTMLDivElement>(null);
  const detailEl = useRef<HTMLDivElement>(null);
  const main = useRef<L.Map>();
  const detail = useRef<L.Map>();
  const resultsGroup = useRef(L.layerGroup());
  const detailGroup = useRef(L.layerGroup());
  const stopDraw = useRef<(() => void) | null>(null);

  const [user, setUser] = useState("anonymous");
  const [features, setFeatures] = useState<Feature[]>([]);
  const [total, setTotal] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [status, setStatus] = useState("Draw a box on the map or choose an area.");
  const token = USERS[user];

  useEffect(() => {
    const m = L.map(mainEl.current!).setView([20, 78], 4);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18, attribution: "© OpenStreetMap contributors" }).addTo(m);
    resultsGroup.current.addTo(m);
    main.current = m;
    const d = L.map(detailEl.current!, { zoomControl: false }).setView([20, 78], 3);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18 }).addTo(d);
    detailGroup.current.addTo(d);
    detail.current = d;
    return () => { m.remove(); d.remove(); };
  }, []);

  async function runSearch(bbox: number[]) {
    setStatus("Searching…");
    try {
      const r = await search(bbox, token);
      setFeatures(r.features);
      setTotal(r.numberMatched);
      setPicked(null);
      const bounds = showResults(resultsGroup.current, r.features, (id) => setPicked(id));
      if (bounds.isValid()) main.current!.fitBounds(bounds, { padding: [20, 20] });
      setStatus(`${r.numberMatched} scenes found.`);
    } catch (e) {
      setStatus(String(e));
    }
  }

  useEffect(() => {
    highlight(resultsGroup.current, features, picked);
    const f = features.find((x) => x.id === picked);
    if (f && detail.current) showDetail(detail.current, detailGroup.current, f, token);
  }, [picked]);

  function drawBox() {
    stopDraw.current?.();
    setStatus("Drag on the map to draw a search box.");
    stopDraw.current = enableBoxDrawing(main.current!, (bbox) => { stopDraw.current = null; runSearch(bbox); });
  }

  const pickedFeature = features.find((f) => f.id === picked);
  return (
    <div className="app">
      <header>
        <b>Orbit Portal</b>
        <span className="who">
          Signed in as&nbsp;
          <select value={user} onChange={(e) => setUser(e.target.value)}>
            {Object.keys(USERS).map((u) => <option key={u}>{u}</option>)}
          </select>
        </span>
      </header>
      <aside>
        <button onClick={drawBox}>Draw search box</button>
        <div className="areas">
          {Object.entries(AREAS).map(([name, bbox]) => <button key={name} onClick={() => runSearch(bbox)}>{name}</button>)}
        </div>
        <p className="status">{status}</p>
        <ul className="results">
          {features.map((f) => (
            <li key={f.id} className={f.id === picked ? "picked" : ""} onClick={() => setPicked(f.id)}>
              <div>{f.properties.name}</div>
              <small>{f.properties.datetime}{f.properties.access !== "public" ? " · " + f.properties.access : ""}</small>
            </li>
          ))}
        </ul>
        {total > features.length && <small>Showing {features.length} of {total}</small>}
      </aside>
      <main ref={mainEl} />
      <section className="detail">
        <h3>Scene detail</h3>
        <div ref={detailEl} className="detailmap" />
        {pickedFeature ? (
          <dl>
            <dt>Name</dt><dd>{pickedFeature.properties.name}</dd>
            <dt>Acquired (UTC)</dt><dd>{pickedFeature.properties.datetime}</dd>
            <dt>Access</dt><dd>{pickedFeature.properties.access}</dd>
            {pickedFeature.properties.has_file && <><dt>File</dt><dd>{((pickedFeature.properties.size_bytes ?? 0) / 1048576).toFixed(0)} MB</dd></>}
          </dl>
        ) : <p>Pick a scene from the list or the map.</p>}
      </section>
    </div>
  );
}
