"""Serves whole or partial scene files. Download tools use the HTTP `Range` header to fetch big files in pieces and to resume."""
import hashlib
import os

from fastapi import Response

_checksums = {}


def parse_range(header, total):
    """'bytes=a-b' -> (start, end) or None when there is no usable range."""
    if not header or not header.startswith("bytes="):
        return None
    a, _, b = header[len("bytes="):].strip().partition("-")
    try:
        start = int(a) if a else 0
        end = int(b) if b else total - 1
    except ValueError:
        return None
    if start >= total or start > end:
        return None
    return start, end


def read_range(path, start, length):
    with open(path, "rb") as f:
        f.seek(start)
        return f.read(length)


def serve_file(path, range_header):
    total = os.path.getsize(path)
    rng = parse_range(range_header, total)
    if rng is None:
        with open(path, "rb") as f:
            return Response(f.read(), media_type="application/octet-stream")
    start, end = rng
    length = end - start
    data = read_range(path, start, length)
    return Response(data, status_code=206, media_type="application/octet-stream",
                    headers={"Content-Range": f"bytes {start}-{end}/{total}"})


def checksum(path):
    if path not in _checksums:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        _checksums[path] = h.hexdigest()
    return {"sha256": _checksums[path], "size": os.path.getsize(path)}
