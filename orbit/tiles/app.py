"""Tile service: map tiles for a scene."""
import os

import psutil
from fastapi import Depends, FastAPI, HTTPException, Response

from orbit.catalog import db as dbmod
from orbit.catalog.auth import can_see, current_user
from orbit.tiles import render
from orbit.tiles.cache import TileCache

app = FastAPI(title="Orbit Portal tiles")
cache = TileCache()
_db = None


def get_db():
    global _db
    if _db is None:
        _db = dbmod.connect()
        dbmod.init_db(_db)
    return _db


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/debug/stats")
def stats():
    """Handy while testing: how much memory the process uses and what the cache holds."""
    return {"rss_mb": round(psutil.Process(os.getpid()).memory_info().rss / 1e6, 1),
            "cache_items": len(cache.items), "cache_mb": round(sum(len(v) for v in cache.items.values()) / 1e6, 1)}


@app.get("/tiles/{scene_id}/{z}/{x}/{y}.png")
def tile(scene_id: str, z: int, x: int, y: int, user=Depends(current_user)):
    row = get_db().execute("SELECT minx, miny, maxx, maxy, restricted_unit, file_path, size_bytes FROM scenes WHERE id = ?", (scene_id,)).fetchone()
    if row is None or not can_see(user[1], row["restricted_unit"]):
        raise HTTPException(status_code=404, detail="scene not found")
    if row["file_path"] and (not os.path.exists(row["file_path"]) or os.path.getsize(row["file_path"]) != row["size_bytes"]):
        raise HTTPException(status_code=404, detail="scene data not available")
    if not (0 <= z <= 20 and 0 <= x < 2 ** z and 0 <= y < 2 ** z):
        raise HTTPException(status_code=400, detail="bad tile")
    parts = render.scene_parts(row["minx"], row["miny"], row["maxx"], row["maxy"])
    if not render.intersects(parts, render.tile_bounds(z, x, y)):
        raise HTTPException(status_code=404, detail="tile outside scene")
    key = (scene_id, z, x, y)
    png = cache.get(key)
    if png is None:
        png = render.render_png(scene_id, parts, z, x, y)
        cache.put(key, png)
    # Tiles of restricted scenes are for that unit only.
    scope = "public" if row["restricted_unit"] is None else "private"
    return Response(png, media_type="image/png", headers={"Cache-Control": f"{scope}, max-age=300"})
