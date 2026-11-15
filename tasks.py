"""Developer helper:  python tasks.py seed | run | test

  seed   create the demo catalog and scene files in ./data
  run    start the catalog, tile and gateway services
  test   run the tests
  make-incoming   create a demo scene file waiting to be imported (data/incoming)
  ingest <file> <scene_id>   import a scene
"""
import os
import subprocess
import sys
import time

from orbit import config

SERVICES = [
    ("catalog", "orbit.catalog.app:app", config.CATALOG_PORT),
    ("tiles", "orbit.tiles.app:app", config.TILES_PORT),
    ("gateway", "orbit.gateway.app:app", config.GATEWAY_PORT),
]


def get_python():
    venv_py_win = os.path.join(os.path.dirname(__file__), ".venv", "Scripts", "python.exe")
    if os.path.exists(venv_py_win):
        return venv_py_win
    venv_py_unix = os.path.join(os.path.dirname(__file__), ".venv", "bin", "python")
    if os.path.exists(venv_py_unix):
        return venv_py_unix
    return sys.executable


def seed():
    from orbit.catalog import seed as seeder
    print("seeded", seeder.seed(), "scenes")


def run():
    py = get_python()
    procs = []
    try:
        for name, app, port in SERVICES:
            cmd = f'"{py}" -m uvicorn {app} --port {port}'
            p = subprocess.Popen(cmd, shell=True)
            procs.append(p)
            print(f"started {name} on port {port}")
        print(f"portal is up: http://127.0.0.1:{config.GATEWAY_PORT}  (press Ctrl+C to stop)")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping services...")
    finally:
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass


def make_incoming():
    import json
    from orbit.catalog import seed as seeder
    os.makedirs("data/incoming", exist_ok=True)
    seeder.write_pattern_file("data/incoming/new_scene_a.bin", 180 * 1024 * 1024, 555)
    with open("data/incoming/new_scene_a.bin.json", "w") as f:
        json.dump({"name": "S1_chennai_20251105_new_a", "acquired": "2025-11-05T00:51:12Z", "bbox": [80.1, 12.9, 80.5, 13.3]}, f)
    print("created data/incoming/new_scene_a.bin (180 MB)")


def ingest():
    py = get_python()
    src, scene_id = sys.argv[2], sys.argv[3]
    sys.exit(subprocess.call(f'"{py}" -m orbit.worker.ingest {src} {scene_id}', shell=True))


def test():
    py = get_python()
    sys.exit(subprocess.call(f'"{py}" -m pytest -q tests', shell=True))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"seed": seed, "run": run, "test": test, "make-incoming": make_incoming, "ingest": ingest}.get(cmd, lambda: print(__doc__))()
