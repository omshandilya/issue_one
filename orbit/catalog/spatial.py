"""Spatial lookups against the R*Tree index."""


"""Spatial lookups against the R*Tree index and polygon geometry algorithms."""
import math


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


def ccw(a, b, c):
    """2D cross product of vector ab and ac."""
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def on_segment(p, a, b):
    """Checks if point p lies on segment ab (assuming collinear)."""
    return (min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and
            min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))


def segments_intersect(p1, p2, p3, p4):
    """Returns True if segment p1-p2 and p3-p4 intersect or touch."""
    d1 = ccw(p3, p4, p1)
    d2 = ccw(p3, p4, p2)
    d3 = ccw(p1, p2, p3)
    d4 = ccw(p1, p2, p4)

    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
       ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True

    if d1 == 0 and on_segment(p1, p3, p4): return True
    if d2 == 0 and on_segment(p2, p3, p4): return True
    if d3 == 0 and on_segment(p3, p1, p2): return True
    if d4 == 0 and on_segment(p4, p1, p2): return True

    return False


def point_in_ring(pt, ring):
    """Ray casting: True if pt is inside or on the boundary of ring."""
    x, y = pt
    inside = False
    n = len(ring) - 1
    for i in range(n):
        p1 = ring[i]
        p2 = ring[i + 1]
        if ccw(p1, p2, pt) == 0 and on_segment(pt, p1, p2):
            return True
        if (p1[1] > y) != (p2[1] > y):
            x_inters = (p2[0] - p1[0]) * (y - p1[1]) / (p2[1] - p1[1]) + p1[0]
            if x <= x_inters:
                inside = not inside
    return inside


def rect_overlaps_ring(rx1, ry1, rx2, ry2, ring):
    """True if rectangle [rx1, ry1, rx2, ry2] intersects or touches ring."""
    rect_verts = [(rx1, ry1), (rx2, ry1), (rx2, ry2), (rx1, ry2)]
    # 1. Any rect vertex inside/on ring?
    for v in rect_verts:
        if point_in_ring(v, ring):
            return True

    # 2. Any ring vertex inside rect?
    for v in ring:
        if rx1 <= v[0] <= rx2 and ry1 <= v[1] <= ry2:
            return True

    # 3. Any edge intersects?
    rect_edges = [
        (rect_verts[0], rect_verts[1]),
        (rect_verts[1], rect_verts[2]),
        (rect_verts[2], rect_verts[3]),
        (rect_verts[3], rect_verts[0]),
    ]
    n = len(ring) - 1
    for i in range(n):
        r_edge = (ring[i], ring[i + 1])
        for edge in rect_edges:
            if segments_intersect(edge[0], edge[1], r_edge[0], r_edge[1]):
                return True

    return False


def rect_inside_ring(rx1, ry1, rx2, ry2, ring):
    """True if all 4 rect vertices are strictly inside ring and no edge intersects ring boundary."""
    rect_verts = [(rx1, ry1), (rx2, ry1), (rx2, ry2), (rx1, ry2)]
    for v in rect_verts:
        if not point_in_ring(v, ring):
            return False
    rect_edges = [
        (rect_verts[0], rect_verts[1]),
        (rect_verts[1], rect_verts[2]),
        (rect_verts[2], rect_verts[3]),
        (rect_verts[3], rect_verts[0]),
    ]
    n = len(ring) - 1
    for i in range(n):
        r_edge = (ring[i], ring[i + 1])
        for edge in rect_edges:
            if segments_intersect(edge[0], edge[1], r_edge[0], r_edge[1]):
                return False
    return True


def rect_overlaps_polygon(rx1, ry1, rx2, ry2, outer_ring, holes):
    if not rect_overlaps_ring(rx1, ry1, rx2, ry2, outer_ring):
        return False
    for hole in holes:
        if rect_inside_ring(rx1, ry1, rx2, ry2, hole):
            return False
    return True


def ring_self_intersects(ring):
    n = len(ring) - 1
    for i in range(n):
        e1_a, e1_b = ring[i], ring[i + 1]
        for j in range(i + 1, n):
            if abs(i - j) == 1 or (i == 0 and j == n - 1):
                # Adjacent edges share a vertex; check for collinear overlap
                shared = ring[i] if (ring[i] == ring[j] or ring[i] == ring[j + 1]) else ring[i + 1]
                other1 = e1_b if shared == e1_a else e1_a
                other2 = ring[j + 1] if shared == ring[j] else ring[j]
                if ccw(shared, other1, other2) == 0:
                    if on_segment(other1, shared, other2) or on_segment(other2, shared, other1):
                        return True
                continue
            e2_a, e2_b = ring[j], ring[j + 1]
            if segments_intersect(e1_a, e1_b, e2_a, e2_b):
                return True
    return False


def unwrap_ring(ring, ref_lon=None):
    """Unwraps longitude coordinates so that crossing the date line is continuous."""
    if not ring:
        return []
    start_lon, start_lat = ring[0]
    if ref_lon is not None:
        diff = start_lon - ref_lon
        while diff > 180.0:
            start_lon -= 360.0
            diff = start_lon - ref_lon
        while diff < -180.0:
            start_lon += 360.0
            diff = start_lon - ref_lon
    unwrapped = [[start_lon, start_lat]]
    for i in range(1, len(ring)):
        lon, lat = ring[i]
        prev_lon = unwrapped[-1][0]
        diff = lon - prev_lon
        while diff > 180.0:
            lon -= 360.0
            diff = lon - prev_lon
        while diff < -180.0:
            lon += 360.0
            diff = lon - prev_lon
        unwrapped.append([lon, lat])
    return unwrapped


def validate_polygon(geom):
    """Validates GeoJSON Polygon. Raises ValueError if invalid."""
    if not isinstance(geom, dict) or geom.get("type") != "Polygon":
        raise ValueError("Geometry type must be 'Polygon'")
    coords = geom.get("coordinates")
    if not isinstance(coords, list) or len(coords) == 0:
        raise ValueError("Polygon must contain at least an outer ring")

    unwrapped_rings = []
    for idx, ring in enumerate(coords):
        if not isinstance(ring, list) or len(ring) < 4:
            raise ValueError(f"Ring {idx} must contain at least 4 coordinates")
        for pt in ring:
            if not (isinstance(pt, (list, tuple)) and len(pt) >= 2 and
                    isinstance(pt[0], (int, float)) and isinstance(pt[1], (int, float))):
                raise ValueError(f"Ring {idx} coordinates must be numbers [lon, lat]")
        if ring[0][0] != ring[-1][0] or ring[0][1] != ring[-1][1]:
            raise ValueError(f"Ring {idx} must be closed (first and last coordinate must match)")
        distinct = set((pt[0], pt[1]) for pt in ring[:-1])
        if len(distinct) < 3:
            raise ValueError(f"Ring {idx} must have at least 3 distinct vertices")

        ref_lon = unwrapped_rings[0][0][0] if unwrapped_rings else None
        unwrapped = unwrap_ring(ring, ref_lon)
        if ring_self_intersects(unwrapped):
            raise ValueError(f"Ring {idx} edges cross each other (self-intersection)")
        unwrapped_rings.append(unwrapped)

    return unwrapped_rings


def bbox_query_intervals(p_minx, p_maxx):
    if p_maxx - p_minx >= 360:
        return [(-180.0, 180.0, 0.0)]
    intervals = []
    k_min = int(math.floor((p_minx + 180.0) / 360.0))
    k_max = int(math.floor((p_maxx + 180.0) / 360.0))
    for k in range(k_min, k_max + 1):
        shift = k * 360.0
        c_min = max(p_minx, -180.0 + shift)
        c_max = min(p_maxx, 180.0 + shift)
        if c_min <= c_max:
            intervals.append((c_min - shift, c_max - shift, shift))
    return intervals


def polygon_candidate_ids(db, geom):
    """Finds all scene IDs whose footprint overlaps the given GeoJSON Polygon."""
    unwrapped_rings = validate_polygon(geom)
    outer_ring = unwrapped_rings[0]
    holes = unwrapped_rings[1:]

    p_minx = min(pt[0] for pt in outer_ring)
    p_maxx = max(pt[0] for pt in outer_ring)
    p_miny = min(pt[1] for pt in outer_ring)
    p_maxy = max(pt[1] for pt in outer_ring)

    intervals = bbox_query_intervals(p_minx, p_maxx)
    candidates = {}  # scene_id -> list of shifts to check

    for q_minx, q_maxx, shift in intervals:
        rows = db.execute(
            "SELECT DISTINCT i.scene_id FROM scene_rtree r JOIN scene_index i ON i.rid = r.rid "
            "WHERE r.minx <= ? AND r.maxx >= ? AND r.miny <= ? AND r.maxy >= ?",
            (q_maxx, q_minx, p_maxy, p_miny),
        ).fetchall()
        for r in rows:
            sid = r["scene_id"]
            candidates.setdefault(sid, set()).add(shift)

    if not candidates:
        return []

    # Fetch geometry bounds for all candidates
    placeholders = ",".join("?" * len(candidates))
    rows = db.execute(f"SELECT id, minx, miny, maxx, maxy FROM scenes WHERE id IN ({placeholders})", list(candidates.keys())).fetchall()

    matching_ids = []
    for r in rows:
        sid = r["id"]
        minx, miny, maxx, maxy = r["minx"], r["miny"], r["maxx"], r["maxy"]
        rects = [(minx, miny, maxx, maxy)] if minx <= maxx else [(minx, miny, 180.0, maxy), (-180.0, miny, maxx, maxy)]

        # Test against polygon with all applicable longitude shifts
        shifts = candidates[sid]
        matched = False
        for shift in shifts:
            for rx1, ry1, rx2, ry2 in rects:
                if rect_overlaps_polygon(rx1 + shift, ry1, rx2 + shift, ry2, outer_ring, holes):
                    matched = True
                    break
            if matched:
                break
        if matched:
            matching_ids.append(sid)

    return matching_ids
