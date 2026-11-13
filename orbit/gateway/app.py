"""Gateway: the one address analysts use. Passes requests to the catalog and tile services and caches answers."""
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from orbit import config
from orbit.gateway import range_proxy
from orbit.gateway.cache import ResponseCache

cache = ResponseCache()
client = None


@asynccontextmanager
async def lifespan(app):
    global client
    client = httpx.AsyncClient(timeout=30)
    yield
    await client.aclose()


app = FastAPI(title="Orbit Portal gateway", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_headers=["authorization", "range"], expose_headers=["content-range", "x-cache"])


async def forward(request: Request, base_url: str):
    """Ask an upstream service, reusing a recent answer when we have one."""
    key = cache.key(request)
    if request.method == "GET":
        hit = cache.get(key)
        if hit:
            _, status, headers, body = hit
            return Response(body, status_code=status, headers={**headers, "X-Cache": "HIT"})
    url = base_url + request.url.path + ("?" + request.url.query if request.url.query else "")
    auth = request.headers.get("authorization")
    up = await client.request(request.method, url, headers={"authorization": auth} if auth else {})
    headers = {k: v for k, v in up.headers.items() if k.lower() in ("content-type", "cache-control")}
    if request.method == "GET" and up.status_code == 200:
        cache.put(key, up.status_code, headers, up.content)
    return Response(up.content, status_code=up.status_code, headers={**headers, "X-Cache": "MISS"})


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/debug/cache")
def debug_cache():
    return {"entries": len(cache.store), "hits": cache.hits, "misses": cache.misses}


@app.get("/search")
async def search(request: Request):
    return await forward(request, config.CATALOG_URL)


@app.get("/tiles/{rest:path}")
async def tiles(request: Request, rest: str):
    return await forward(request, config.TILES_URL)


async def visible_file(request: Request, scene_id: str):
    """Only serve a file to someone who is allowed to see the scene (the catalog decides)."""
    auth = request.headers.get("authorization")
    up = await client.get(f"{config.CATALOG_URL}/scenes/{scene_id}", headers={"authorization": auth} if auth else {})
    if up.status_code != 200:
        raise HTTPException(status_code=up.status_code, detail="scene not found")
    if not up.json()["properties"].get("has_file"):
        raise HTTPException(status_code=404, detail="no file for this scene")
    return f"{config.FILES_DIR}/{scene_id}.bin"


@app.get("/scenes/{scene_id}/file")
async def scene_file(request: Request, scene_id: str):
    path = await visible_file(request, scene_id)
    return range_proxy.serve_file(path, request.headers.get("range"))


@app.get("/scenes/{scene_id}/checksum")
async def scene_checksum(request: Request, scene_id: str):
    path = await visible_file(request, scene_id)
    return range_proxy.checksum(path)


@app.get("/scenes/{scene_id}")
async def scene(request: Request, scene_id: str):
    return await forward(request, config.CATALOG_URL)
