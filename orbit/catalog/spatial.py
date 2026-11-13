"""Spatial lookups against the R*Tree index."""


def candidate_ids(db, min_lon, min_lat, max_lon, max_lat):
    """Ids of scenes whose footprint intersects the box."""
    if min_lon > max_lon:
        boxes = [(min_lon, 180.0), (-180.0, max_lon)]
    else:
        boxes = [(min_lon, max_lon)]
    ids = set()
    for lo, hi in boxes:
        rows = db.execute(
            "SELECT DISTINCT i.scene_id FROM scene_rtree r JOIN scene_index i ON i.rid = r.rid "
            "WHERE r.minx <= ? AND r.maxx >= ? AND r.miny <= ? AND r.maxy >= ?",
            (hi, lo, max_lat, min_lat),
        ).fetchall()
        for r in rows:
            ids.add(r["scene_id"])
    return list(ids)
