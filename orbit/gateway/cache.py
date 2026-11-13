"""Response cache for the gateway: repeated requests for the same thing are answered without bothering the services."""
import re
import time


class ResponseCache:
    def __init__(self):
        self.store = {}           # key -> (expires_at, status, headers, body)
        self.hits = 0
        self.misses = 0

    @staticmethod
    def key(request):
        return request.method + request.url.path + "?" + request.url.query

    @staticmethod
    def max_age(cache_control):
        m = re.search(r"max-age=(\d+)", cache_control or "")
        return int(m.group(1)) if m else 0

    def get(self, key):
        entry = self.store.get(key)
        if entry and entry[0] > time.time():
            self.hits += 1
            return entry
        self.misses += 1
        return None

    def put(self, key, status, headers, body):
        age = self.max_age(headers.get("cache-control"))
        if age > 0:
            self.store[key] = (time.time() + age, status, headers, body)
