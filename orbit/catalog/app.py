"""Catalog API: search scenes by area and time."""
import json
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, Response

from orbit.catalog import db as dbmod
from orbit.catalog.auth import can_see, current_user
from orbit.catalog.spatial import candidate_ids

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
    return a


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
    response.headers["Cache-Control"] = "public, max-age=60"
    return {"type": "FeatureCollection", "numberMatched": len(rows), "numberReturned": len(page),
            "features": [to_feature(r, user[1]) for r in page]}


@app.get("/scenes/{scene_id}")
def scene(scene_id: str, response: Response, user=Depends(current_user)):
    row = get_db().execute("SELECT * FROM scenes WHERE id = ?", (scene_id,)).fetchone()
    if row is None or not can_see(user[1], row["restricted_unit"]):
        raise HTTPException(status_code=404, detail="scene not found")
    response.headers["Cache-Control"] = "public, max-age=60"
    return to_feature(row, user[1])
