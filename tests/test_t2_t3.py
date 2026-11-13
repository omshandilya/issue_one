import pytest
from fastapi.testclient import TestClient

from orbit.gateway.cache import ResponseCache


@pytest.fixture(scope="module")
def catalog():
    from orbit.catalog.app import app
    return TestClient(app)


def test_t2_search_across_dateline_fiji(catalog):
    # Fiji box crossing the date line: 177 E to 178 W (-178)
    r = catalog.get("/search", params={"bbox": "177,-20,-178,-15"})
    assert r.status_code == 200
    data = r.json()
    assert data["numberMatched"] == 12
    assert len(data["features"]) == 12


def test_t2_search_fiji_unwrapped_coords(catalog):
    # Unwrapped coordinates (e.g. 182 lon instead of -178)
    r = catalog.get("/search", params={"bbox": "177,-20,182,-15"})
    assert r.status_code == 200
    assert r.json()["numberMatched"] == 12


def test_t3_gateway_cache_key_varies_by_auth():
    class DummyRequest:
        def __init__(self, method, path, query, auth=None):
            self.method = method
            self.url = type("URL", (), {"path": path, "query": query})()
            self.headers = {"authorization": auth} if auth else {}

    req_a = DummyRequest("GET", "/search", "bbox=69.0,22.0,70.5,23.5", "Bearer tok-analyst-a-7f3c")
    req_b = DummyRequest("GET", "/search", "bbox=69.0,22.0,70.5,23.5", "Bearer tok-analyst-b-91d2")
    req_anon = DummyRequest("GET", "/search", "bbox=69.0,22.0,70.5,23.5", None)

    cache = ResponseCache()
    key_a = cache.key(req_a)
    key_b = cache.key(req_b)
    key_anon = cache.key(req_anon)

    # Different authorization contexts must have distinct cache keys
    assert key_a != key_b
    assert key_a != key_anon
    assert key_b != key_anon


def test_t3_catalog_headers_and_isolation(catalog):
    kutch_bbox = "69.0,22.0,70.5,23.5"

    # Analyst A gets public + Unit A restricted scenes
    res_a = catalog.get("/search", params={"bbox": kutch_bbox}, headers={"authorization": "Bearer tok-analyst-a-7f3c"})
    assert res_a.status_code == 200
    features_a = res_a.json()["features"]
    assert any("Unit A" in f["properties"]["access"] for f in features_a)
    assert res_a.headers.get("vary") == "Authorization"
    assert "private" in res_a.headers.get("cache-control", "")

    # Analyst B must NEVER see Unit A restricted scenes
    res_b = catalog.get("/search", params={"bbox": kutch_bbox}, headers={"authorization": "Bearer tok-analyst-b-91d2"})
    assert res_b.status_code == 200
    features_b = res_b.json()["features"]
    assert all(f["properties"]["access"] == "public" for f in features_b)

