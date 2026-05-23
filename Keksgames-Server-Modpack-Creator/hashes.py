from __future__ import annotations

import hashlib
from pathlib import Path


def sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def curseforge_fingerprint(path: Path) -> int:
    data = path.read_bytes()
    filtered = bytes(byte for byte in data if byte not in (9, 10, 13, 32))
    return murmurhash2(filtered, seed=1)


def murmurhash2(data: bytes, seed: int = 1) -> int:
    m = 0x5BD1E995
    r = 24
    length = len(data)
    h = (seed ^ length) & 0xFFFFFFFF
    offset = 0

    while length >= 4:
        k = (
            data[offset]
            | (data[offset + 1] << 8)
            | (data[offset + 2] << 16)
            | (data[offset + 3] << 24)
        )
        k = (k * m) & 0xFFFFFFFF
        k ^= (k >> r)
        k = (k * m) & 0xFFFFFFFF

        h = (h * m) & 0xFFFFFFFF
        h ^= k

        offset += 4
        length -= 4

    if length == 3:
        h ^= data[offset + 2] << 16
    if length >= 2:
        h ^= data[offset + 1] << 8
    if length >= 1:
        h ^= data[offset]
        h = (h * m) & 0xFFFFFFFF

    h ^= h >> 13
    h = (h * m) & 0xFFFFFFFF
    h ^= h >> 15
    return h & 0xFFFFFFFF
