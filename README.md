# Problem 1: Orbit Portal

This is a **prototype** of a real software product: a web app for searching satellite images on a map, built for a disaster-response agency. The code was written by someone else and has been **handed over to you as it is** (the whole codebase is in this folder). The customer has since filed tickets: read **`TICKETS.md`** first. Your job is described in the main `README.md` one folder up.

## What is in here

| Part | Folder | What it does |
|---|---|---|
| Catalog API | `orbit/catalog/` | Search scenes by area and time (SQLite database) |
| Tile service | `orbit/tiles/` | Draws the map tiles for a scene |
| Gateway | `orbit/gateway/` | The one address analysts use; passes requests on and caches answers |
| Import worker | `orbit/worker/` | Imports a new scene (`python -m orbit.worker.ingest <file> <scene_id>`) |
| Web app | `web/` | The page analysts see (React, TypeScript, Leaflet map) |
| API notes | `docs/api.md` | Routes, including the new ones the feature ticket asks for |
| Test accounts | `seed/users.md` | Who can see what |
| Tests | `tests/` | A few quick tests; they pass today |

## Set it up

**Run every command from this folder, and run `python tasks.py seed` once before anything else**: the services and tests read the demo data from `./data`, which does not exist until you create it.

You need Python 3.11+ and Node 20+.

```
# from this folder
python -m venv .venv
# Windows:        .venv\Scripts\activate
# Mac / Linux:    source .venv/bin/activate
pip install -r requirements.txt

python tasks.py seed          # creates the demo scenes in ./data (takes a few seconds)

cd web
npm install
cd ..
```

## Run it

Three services and the web page. Open four terminals (with the virtual environment active in the first three), all from this folder:

```
python -m uvicorn orbit.catalog.app:app --port 8001
python -m uvicorn orbit.tiles.app:app --port 8002
python -m uvicorn orbit.gateway.app:app --port 8000
cd web && npm run dev            # then open http://127.0.0.1:5173
```

(`python tasks.py run` starts the three services together.)

Run the tests with `python -m pytest -q tests`.

## Handy for reproducing the tickets

- The seeded demo data has Mumbai, the Gulf of Kutch, the Odisha coast and Fiji; boxes you can paste are in `seed/users.md`.
- `python tasks.py make-incoming` creates a scene file waiting to be imported (`data/incoming/`), for the import ticket.
- `ORBIT_FAULT_KILL_AFTER_BYTES=50000000` makes an import stop dead after about 50 MB, like a power cut. Keep this switch working: our tests use it.
- `GET http://127.0.0.1:8002/debug/stats` shows the tile service's memory use and cache size; `GET http://127.0.0.1:8000/debug/cache` shows the gateway cache.
- The tile cache size can be set with `ORBIT_TILE_CACHE_MB`.

## Rules that apply to all tickets

See "Rules that apply to every ticket" at the top of `TICKETS.md`: which names and commands must keep working so our automatic tests can run against your code.
