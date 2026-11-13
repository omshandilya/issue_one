"""Serves whole or partial scene files. Download tools use the HTTP `Range` header to fetch big files in pieces and to resume."""
import hashlib
import os

from fastapi import Response

_checksums = {}


def parse_range(header, total):
    """'bytes=a-b' -> (start, end) or None when there is no usable range."""
    if not header or not header.startswith("bytes="):
        return None
    val = header[len("bytes="):].strip()
    if "," in val:
        # Multiple ranges not supported; take the first range
        val = val.split(",", 1)[0].strip()
    a, _, b = val.partition("-")
    try:
        if not a and b:
            # Suffix range: bytes=-500 means last 500 bytes
            suffix = int(b)
            if suffix <= 0:
                return None
            start = max(0, total - suffix)
            end = total - 1
            return start, end
        start = int(a) if a else 0
        end = int(b) if b else total - 1
    except ValueError:
        return None
    if start >= total or start > end:
        return None
    end = min(end, total - 1)
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
            return Response(f.read(), media_type="application/octet-stream",
                            headers={"Accept-Ranges": "bytes", "Content-Length": str(total)})
    start, end = rng
    length = end - start + 1
    data = read_range(path, start, length)
    return Response(data, status_code=206, media_type="application/octet-stream",
                    headers={"Content-Range": f"bytes {start}-{end}/{total}",
                             "Accept-Ranges": "bytes",
                             "Content-Length": str(length)})


def checksum(path):
    if path not in _checksums:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        _checksums[path] = h.hexdigest()
    return {"sha256": _checksums[path], "size": os.path.getsize(path)}
