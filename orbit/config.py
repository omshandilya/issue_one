"""Orbit Portal settings."""
import os

# Where the portal keeps its data (catalog database, scene files).
DATA_DIR = os.environ.get("ORBIT_DATA_DIR", "./data")
DB_PATH = DATA_DIR + "/catalog.db"
FILES_DIR = DATA_DIR + "/files"

# Service addresses. The gateway is the only one analysts talk to.
GATEWAY_PORT = int(os.environ.get("ORBIT_GATEWAY_PORT", "8000"))
CATALOG_PORT = int(os.environ.get("ORBIT_CATALOG_PORT", "8001"))
TILES_PORT = int(os.environ.get("ORBIT_TILES_PORT", "8002"))
CATALOG_URL = os.environ.get("ORBIT_CATALOG_URL", f"http://127.0.0.1:{CATALOG_PORT}")
TILES_URL = os.environ.get("ORBIT_TILES_URL", f"http://127.0.0.1:{TILES_PORT}")

# Tile cache size in megabytes.
TILE_CACHE_MB = int(os.environ.get("ORBIT_TILE_CACHE_MB", "256"))

# Seconds the gateway may reuse an answer it has already seen.
DEFAULT_CACHE_SECONDS = 60
