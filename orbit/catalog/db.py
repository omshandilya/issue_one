"""SQLite catalog with an R*Tree spatial index."""
import json
import os
import sqlite3

from orbit import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS scenes (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    acquired        TEXT NOT NULL,          -- ISO 8601, always UTC, e.g. 2025-03-01T01:03:25Z
    minx REAL, miny REAL, maxx REAL, maxy REAL,
    restricted_unit TEXT,                   -- NULL = public; otherwise only that unit may see it
    footprint       TEXT NOT NULL,          -- GeoJSON geometry, [lon, lat]
    file_path       TEXT,
    size_bytes      INTEGER
);
CREATE VIRTUAL TABLE IF NOT EXISTS scene_rtree USING rtree(rid, minx, maxx, miny, maxy);
CREATE TABLE IF NOT EXISTS scene_index (rid INTEGER PRIMARY KEY, scene_id TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS scenes_acquired ON scenes(acquired);
CREATE TABLE IF NOT EXISTS polygon_searches (
    search_id       TEXT PRIMARY KEY,
    user_name       TEXT,
    unit            TEXT,
    created_at      TEXT NOT NULL,
    scene_ids       TEXT NOT NULL
);
"""


def connect(path=None):
    path = path or config.DB_PATH
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    db = sqlite3.connect(path, check_same_thread=False)
    db.row_factory = sqlite3.Row
    return db


def init_db(db):
    db.executescript(SCHEMA)
    db.commit()


def _rect(minx, miny, maxx, maxy):
    return [[minx, miny], [maxx, miny], [maxx, maxy], [minx, maxy], [minx, miny]]


def footprint_geometry(minx, miny, maxx, maxy):
    """A box. A scene that crosses the date line (minx > maxx) is a MultiPolygon with one part per side."""
    if minx <= maxx:
        return {"type": "Polygon", "coordinates": [_rect(minx, miny, maxx, maxy)]}
    return {"type": "MultiPolygon", "coordinates": [[_rect(minx, miny, 180.0, maxy)], [_rect(-180.0, miny, maxx, maxy)]]}


def add_scene(db, scene_id, name, acquired, minx, miny, maxx, maxy, restricted_unit=None, file_path=None, size_bytes=None):
    # Clean up any existing rtree/index entries for this scene_id to prevent duplicates on re-import
    db.execute("DELETE FROM scene_rtree WHERE rid IN (SELECT rid FROM scene_index WHERE scene_id = ?)", (scene_id,))
    db.execute("DELETE FROM scene_index WHERE scene_id = ?", (scene_id,))
    db.execute(
        "INSERT OR REPLACE INTO scenes (id, name, acquired, minx, miny, maxx, maxy, restricted_unit, footprint, file_path, size_bytes) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (scene_id, name, acquired, minx, miny, maxx, maxy, restricted_unit,
         json.dumps(footprint_geometry(minx, miny, maxx, maxy)), file_path, size_bytes))
    # Index entries: a scene that crosses the date line is stored as two boxes, one per side.
    parts = [(minx, maxx)] if minx <= maxx else [(minx, 180.0), (-180.0, maxx)]
    for lo, hi in parts:
        cur = db.execute("INSERT INTO scene_index (scene_id) VALUES (?)", (scene_id,))
        db.execute("INSERT INTO scene_rtree (rid, minx, maxx, miny, maxy) VALUES (?,?,?,?,?)", (cur.lastrowid, lo, hi, miny, maxy))
