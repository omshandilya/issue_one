import csv
import io
import json
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def catalog():
    from orbit.catalog.app import app
    return TestClient(app)


def test_f1_polygon_search_basic(catalog):
    # Mumbai polygon
    poly = {
        "type": "Polygon",
        "coordinates": [
            [[72.6, 18.7], [73.2, 18.7], [73.2, 19.3], [72.6, 19.3], [72.6, 18.7]]
        ]
    }
    r = catalog.post("/search/polygon", json=poly)
    assert r.status_code == 200
    data = r.json()
    assert "search_id" in data
    assert data["numberMatched"] > 0
    assert len(data["features"]) == min(100, data["numberMatched"])


def test_f1_polygon_validation_errors(catalog):
    # 1. Wrong type
    r1 = catalog.post("/search/polygon", json={"type": "Point", "coordinates": [0, 0]})
    assert r1.status_code == 400
    assert "Polygon" in r1.json()["detail"]

    # 2. Ring not closed
    r2 = catalog.post("/search/polygon", json={
        "type": "Polygon",
        "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]
    })
    assert r2.status_code == 400
    assert "closed" in r2.json()["detail"]

    # 3. Fewer than 3 distinct points
    r3 = catalog.post("/search/polygon", json={
        "type": "Polygon",
        "coordinates": [[[0, 0], [1, 1], [0, 0], [0, 0]]]
    })
    assert r3.status_code == 400

    # 4. Self-intersecting edges (figure 8 / bowtie)
    r4 = catalog.post("/search/polygon", json={
        "type": "Polygon",
        "coordinates": [
            [[0, 0], [2, 2], [0, 2], [2, 0], [0, 0]]
        ]
    })
    assert r4.status_code == 400
    assert "self-intersection" in r4.json()["detail"] or "cross" in r4.json()["detail"]


def test_f1_polygon_with_hole(catalog):
    # Outer ring covering Mumbai, inner hole covering the central port area
    poly = {
        "type": "Polygon",
        "coordinates": [
            [[72.0, 18.0], [74.0, 18.0], [74.0, 20.0], [72.0, 20.0], [72.0, 18.0]],
            # Hole exactly over the scenes
            [[72.65, 18.75], [73.25, 18.75], [73.25, 19.35], [72.65, 19.35], [72.65, 18.75]]
        ]
    }
    r = catalog.post("/search/polygon", json=poly)
    assert r.status_code == 200
    # Scenes inside the hole should not match
    data = r.json()
    assert data["numberMatched"] == 0


def test_f1_polygon_across_dateline_fiji(catalog):
    # Fiji shape crossing the date line
    poly = {
        "type": "Polygon",
        "coordinates": [
            [[177.0, -20.0], [-178.0, -20.0], [-178.0, -15.0], [177.0, -15.0], [177.0, -20.0]]
        ]
    }
    r = catalog.post("/search/polygon", json=poly)
    assert r.status_code == 200
    data = r.json()
    assert data["numberMatched"] == 12


def test_f1_export_geojson_and_csv_streaming(catalog):
    poly = {
        "type": "Polygon",
        "coordinates": [
            [[72.6, 18.7], [73.2, 18.7], [73.2, 19.3], [72.6, 19.3], [72.6, 18.7]]
        ]
    }
    # Run search as analyst_a
    auth = {"authorization": "Bearer tok-analyst-a-7f3c"}
    res = catalog.post("/search/polygon", json=poly, headers=auth)
    assert res.status_code == 200
    search_id = res.json()["search_id"]
    count = res.json()["numberMatched"]

    # 1. Export CSV
    r_csv = catalog.get(f"/export/{search_id}?format=csv", headers=auth)
    assert r_csv.status_code == 200
    assert r_csv.headers["content-type"].startswith("text/csv")
    csv_reader = csv.reader(io.StringIO(r_csv.text))
    rows = list(csv_reader)
    header = rows[0]
    assert header == ["id", "name", "datetime", "access", "min_lon", "min_lat", "max_lon", "max_lat"]
    assert len(rows) - 1 == count
    # Datetime should end in 'Z'
    assert all(row[2].endswith("Z") for row in rows[1:])

    # 2. Export GeoJSON
    r_geo = catalog.get(f"/export/{search_id}?format=geojson", headers=auth)
    assert r_geo.status_code == 200
    assert "geo+json" in r_geo.headers["content-type"]
    geo_data = json.loads(r_geo.text)
    assert geo_data["type"] == "FeatureCollection"
    assert len(geo_data["features"]) == count

    # 3. Ownership security: analyst_b cannot export analyst_a's search
    auth_b = {"authorization": "Bearer tok-analyst-b-91d2"}
    r_bad_user = catalog.get(f"/export/{search_id}?format=csv", headers=auth_b)
    assert r_bad_user.status_code == 404

    # 4. Unknown search_id -> 404
    assert catalog.get("/export/nonexistent_id?format=csv", headers=auth).status_code == 404

    # 5. Bad format -> 400
    assert catalog.get(f"/export/{search_id}?format=parquet", headers=auth).status_code == 400

