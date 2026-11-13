"""In-memory cache for rendered tiles."""
import os
from collections import OrderedDict

from orbit import config


class TileCache:
    """Keeps recently used tiles so busy areas of the map load instantly."""

    def __init__(self, max_items=None, max_mb=None):
        self.items = OrderedDict()        # key -> tile bytes (ordered from oldest to newest)
        self.max_items = max_items
        env_mb = os.environ.get("ORBIT_TILE_CACHE_MB")
        mb = max_mb if max_mb is not None else (int(env_mb) if env_mb else getattr(config, "TILE_CACHE_MB", 256))
        self.max_bytes = int(mb * 1024 * 1024) if mb is not None else None
        self.current_bytes = 0

    def get(self, k):
        if k in self.items:
            self.items.move_to_end(k)
            return self.items[k]
        return None

    def put(self, k, v):
        if k in self.items:
            self.current_bytes -= len(self.items[k])
        self.items[k] = v
        self.items.move_to_end(k)
        self.current_bytes += len(v)

        while self.items and (
            (self.max_bytes is not None and self.current_bytes > self.max_bytes) or
            (self.max_items is not None and len(self.items) > self.max_items)
        ):
            _, old_v = self.items.popitem(last=False)
            self.current_bytes -= len(old_v)
