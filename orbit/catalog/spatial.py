"""Spatial lookups against the R*Tree index."""


def candidate_ids(db, min_lon, min_lat, max_lon, max_lat):
    """Ids of scenes whose footprint intersects the box."""
    rows = db.execute(
        "SELECT DISTINCT i.scene_id FROM scene_rtree r JOIN scene_index i ON i.rid = r.rid "
        "WHERE r.minx <= ? AND r.maxx >= ? AND r.miny <= ? AND r.maxy >= ?",
        (max_lon, min_lon, max_lat, min_lat),
    ).fetchall()
    return [r["scene_id"] for r in rows]
