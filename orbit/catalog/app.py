"""Catalog API: search scenes by area and time."""
import json
import uuid
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse

from orbit.catalog import db as dbmod
from orbit.catalog.auth import can_see, current_user
from orbit.catalog.spatial import candidate_ids, polygon_candidate_ids

app = FastAPI(title="Orbit Portal catalog")
_db = None


def get_db():
    global _db
    if _db is None:
        _db = dbmod.connect()
        dbmod.init_db(_db)
    return _db


def parse_bbox(text):
    try:
        a = [float(x) for x in text.split(",")]
        assert len(a) == 4
    except Exception:
        raise HTTPException(status_code=400, detail="bbox must be min_lon,min_lat,max_lon,max_lat")
    min_lon, min_lat, max_lon, max_lat = a
    if max_lon - min_lon >= 360:
        min_lon, max_lon = -180.0, 180.0
    else:
        def norm(lon):
            if -180.0 <= lon <= 180.0:
                return lon
            w = ((lon + 180.0) % 360.0) - 180.0
            return 180.0 if w == -180.0 and lon > 0 else w
        min_lon, max_lon = norm(min_lon), norm(max_lon)
    return [min_lon, min_lat, max_lon, max_lat]


def parse_time(text):
    """ISO 8601. A time with no zone is taken as UTC."""
    t = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def to_feature(row, unit):
    props = {"id": row["id"], "name": row["name"], "datetime": row["acquired"],
             "access": "public" if row["restricted_unit"] is None else f"RESTRICTED - Coast Guard Unit {row['restricted_unit']}",
             "has_file": row["file_path"] is not None, "size_bytes": row["size_bytes"]}
    return {"type": "Feature", "id": row["id"], "geometry": json.loads(row["footprint"]), "properties": props}


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/search")
def search(response: Response, bbox: str = Query(...), datetime_range: str = Query(None, alias="datetime"),
           limit: int = 100, offset: int = 0, user=Depends(current_user)):
    min_lon, min_lat, max_lon, max_lat = parse_bbox(bbox)
    db = get_db()
    ids = candidate_ids(db, min_lon, min_lat, max_lon, max_lat)
    rows = []
    if ids:
        q = "SELECT * FROM scenes WHERE id IN (%s)" % ",".join("?" * len(ids))
        args = list(ids)
        if datetime_range:
            start, _, end = datetime_range.partition("/")
            if start:
                q += " AND acquired >= ?"; args.append(parse_time(start).strftime("%Y-%m-%dT%H:%M:%SZ"))
            if end:
                q += " AND acquired <= ?"; args.append(parse_time(end).strftime("%Y-%m-%dT%H:%M:%SZ"))
        q += " ORDER BY acquired DESC, id"
        rows = [r for r in db.execute(q, args).fetchall() if can_see(user[1], r["restricted_unit"])]
    page = rows[offset:offset + limit]
    has_restricted = any(r["restricted_unit"] is not None for r in rows)
    scope = "private" if has_restricted or user[1] is not None else "public"
    response.headers["Cache-Control"] = f"{scope}, max-age=60"
    response.headers["Vary"] = "Authorization"
    return {"type": "FeatureCollection", "numberMatched": len(rows), "numberReturned": len(page),
            "features": [to_feature(r, user[1]) for r in page]}


@app.get("/scenes/{scene_id}")
def scene(scene_id: str, response: Response, user=Depends(current_user)):
    row = get_db().execute("SELECT * FROM scenes WHERE id = ?", (scene_id,)).fetchone()
    if row is None or not can_see(user[1], row["restricted_unit"]):
        raise HTTPException(status_code=404, detail="scene not found")
    scope = "public" if row["restricted_unit"] is None else "private"
    response.headers["Cache-Control"] = f"{scope}, max-age=60"
    response.headers["Vary"] = "Authorization"
    return to_feature(row, user[1])


@app.post("/search/polygon")
async def search_polygon(request: Request, response: Response, limit: int = 100, offset: int = 0, user=Depends(current_user)):
    try:
        geom = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    db = get_db()
    try:
        matched_ids = polygon_candidate_ids(db, geom)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    rows = []
    if matched_ids:
        q = "SELECT * FROM scenes WHERE id IN (%s) ORDER BY acquired DESC, id" % ",".join("?" * len(matched_ids))
        rows = [r for r in db.execute(q, matched_ids).fetchall() if can_see(user[1], r["restricted_unit"])]

    search_id = uuid.uuid4().hex[:12]
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    final_ids = [r["id"] for r in rows]
    db.execute(
        "INSERT INTO polygon_searches (search_id, user_name, unit, created_at, scene_ids) VALUES (?,?,?,?,?)",
        (search_id, user[0], user[1], now_iso, json.dumps(final_ids))
    )
    db.commit()

    page = rows[offset:offset + limit]
    return {
        "search_id": search_id,
        "numberMatched": len(rows),
        "numberReturned": len(page),
        "features": [to_feature(r, user[1]) for r in page]
    }


@app.get("/export/{search_id}")
def export(search_id: str, format: str = Query(...), user=Depends(current_user)):
    fmt = format.lower()
    if fmt not in ("geojson", "csv"):
        raise HTTPException(status_code=400, detail="format must be geojson or csv")

    db = get_db()
    search_row = db.execute(
        "SELECT * FROM polygon_searches WHERE search_id = ?",
        (search_id,)
    ).fetchone()

    if search_row is None:
        raise HTTPException(status_code=404, detail="search not found")

    if search_row["user_name"] != user[0]:
        raise HTTPException(status_code=404, detail="search not found")

    scene_ids = json.loads(search_row["scene_ids"])

    if fmt == "csv":
        def generate_csv():
            yield "id,name,datetime,access,min_lon,min_lat,max_lon,max_lat\r\n"
            for i in range(0, len(scene_ids), 200):
                batch = scene_ids[i:i + 200]
                q = f"SELECT * FROM scenes WHERE id IN ({','.join('?' * len(batch))})"
                mapping = {r["id"]: r for r in db.execute(q, batch).fetchall()}
                for sid in batch:
                    r = mapping.get(sid)
                    if not r:
                        continue
                    access = "public" if r["restricted_unit"] is None else f"RESTRICTED - Coast Guard Unit {r['restricted_unit']}"
                    name = r["name"].replace('"', '""')
                    if ',' in name or '"' in name or '\n' in name or '\r' in name:
                        name = f'"{name}"'
                    dt = r["acquired"]
                    yield f"{r['id']},{name},{dt},{access},{r['minx']},{r['miny']},{r['maxx']},{r['maxy']}\r\n"

        return StreamingResponse(
            generate_csv(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="export-{search_id}.csv"'}
        )
    else:
        def generate_geojson():
            yield '{"type": "FeatureCollection", "features": [\n'
            first = True
            for i in range(0, len(scene_ids), 200):
                batch = scene_ids[i:i + 200]
                q = f"SELECT * FROM scenes WHERE id IN ({','.join('?' * len(batch))})"
                mapping = {r["id"]: r for r in db.execute(q, batch).fetchall()}
                for sid in batch:
                    r = mapping.get(sid)
                    if not r:
                        continue
                    feat = to_feature(r, search_row["unit"])
                    chunk = ("" if first else ",\n") + json.dumps(feat)
                    first = False
                    yield chunk
            yield '\n]}'

        return StreamingResponse(
            generate_geojson(),
            media_type="application/geo+json",
            headers={"Content-Disposition": f'attachment; filename="export-{search_id}.geojson"'}
        )
