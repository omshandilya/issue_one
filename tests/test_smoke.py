"""Smoke tests: the basics work."""
import os

import pytest
from fastapi.testclient import TestClient

from orbit.gateway import range_proxy
from orbit.tiles.cache import TileCache

MUMBAI = "72.7,18.8,73.0,19.1"


@pytest.fixture(scope="module")
def catalog():
    from orbit.catalog.app import app
    return TestClient(app)


@pytest.fixture(scope="module")
def tiles():
    from orbit.tiles.app import app
    return TestClient(app)


def test_search_mumbai(catalog):
    r = catalog.get("/search", params={"bbox": MUMBAI})
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "FeatureCollection"
    assert body["numberMatched"] > 0


def test_search_dates(catalog):
    r = catalog.get("/search", params={"bbox": MUMBAI, "datetime": "2025-01-01T00:00:00Z/2025-02-01T00:00:00Z"})
    assert r.status_code == 200
    assert all(f["properties"]["datetime"] < "2025-02-01T00:00:00Z" for f in r.json()["features"])


def test_scene_detail(catalog):
    first = catalog.get("/search", params={"bbox": MUMBAI}).json()["features"][0]["id"]
    assert catalog.get(f"/scenes/{first}").json()["properties"]["id"] == first


def test_bad_token_rejected(catalog):
    assert catalog.get("/search", params={"bbox": MUMBAI}, headers={"authorization": "Bearer nope"}).status_code == 401


def test_restricted_hidden_from_anonymous(catalog):
    feats = catalog.get("/search", params={"bbox": "69.0,22.0,70.5,23.5"}).json()["features"]
    assert all(f["properties"]["access"] == "public" for f in feats)


def test_tile_renders(catalog, tiles):
    sid = catalog.get("/search", params={"bbox": MUMBAI}).json()["features"][0]["id"]
    # a tile over Mumbai at zoom 8
    r = tiles.get(f"/tiles/{sid}/8/178/112.png")
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert r.content[:4] == b"\x89PNG"


def test_tile_cache_stores_and_returns():
    c = TileCache(max_items=10)
    c.put("a", b"1")
    assert c.get("a") == b"1"
    assert c.get("missing") is None


def test_whole_file_download():
    from orbit import config
    path = f"{config.FILES_DIR}/S1_kochi_20251012_small_a.bin"
    assert range_proxy.serve_file(path, None).status_code == 200
