"""In-memory cache for rendered tiles."""


class TileCache:
    """Keeps recently used tiles so busy areas of the map load instantly."""

    def __init__(self, max_items=50000):
        self.items = {}           # key -> tile bytes
        self.order = []           # keys, oldest first
        self.max_items = max_items

    def get(self, k):
        if k in self.items:
            self.order.remove(k)
            self.order.append(k)
            return self.items[k]
        return None

    def put(self, k, v):
        self.items[k] = v
        self.order.append(k)
        if len(self.order) > self.max_items:
            old = self.order.pop()
            self.items.pop(old, None)
