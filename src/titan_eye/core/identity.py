"""Identidad content-addressable.

Todo artefacto crudo y toda detección derivada se identifican por el SHA-256
de su contenido canónico, no por un id autoincremental. Esto es el fundamento
de la procedencia verificable (ADR-0005): dos personas que ingieren los mismos
bytes públicos obtienen el mismo hash, y cualquier alteración es detectable.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def content_hash_bytes(payload: bytes) -> str:
    """SHA-256 hex de un payload crudo (los bytes exactos de la fuente)."""
    return hashlib.sha256(payload).hexdigest()


def canonical_json(obj: Any) -> bytes:
    """Serialización JSON canónica determinista para hashing de modelos.

    Claves ordenadas, sin espacios superfluos, UTF-8, sin NaN/Infinity. Dos
    objetos equivalentes producen exactamente los mismos bytes, en cualquier
    máquina (precondición de P1, reproducibilidad bajo entorno declarado).
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def content_hash_obj(obj: Any) -> str:
    """SHA-256 hex sobre la forma JSON canónica de un objeto serializable."""
    return content_hash_bytes(canonical_json(obj))
