"""Tests del núcleo de identidad content-addressable (ADR-0005)."""

from __future__ import annotations

from titan_eye.core.identity import canonical_json, content_hash_bytes, content_hash_obj


def test_content_hash_bytes_is_sha256_hex() -> None:
    h = content_hash_bytes(b"")
    # SHA-256 del string vacío, valor canónico conocido.
    assert h == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_canonical_json_is_order_independent() -> None:
    a = canonical_json({"b": 1, "a": 2})
    b = canonical_json({"a": 2, "b": 1})
    assert a == b == b'{"a":2,"b":1}'


def test_content_hash_obj_is_deterministic() -> None:
    obj = {"domain": "aerial", "icao24": "abc123", "lat": 49.5, "lon": 33.0}
    assert content_hash_obj(obj) == content_hash_obj(dict(reversed(list(obj.items()))))


def test_different_content_different_hash() -> None:
    assert content_hash_obj({"x": 1}) != content_hash_obj({"x": 2})
