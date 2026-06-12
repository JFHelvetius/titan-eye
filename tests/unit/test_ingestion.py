"""Tests de la cadena de ingestión sin red: artefacto, cache, transporte, fuente."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tests.unit.fixtures_opensky import opensky_payload
from titan_eye.core.domains import Domain
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.identity import content_hash_bytes
from titan_eye.core.timebase import FixedClock
from titan_eye.ingestion.artifact import RawArtifact
from titan_eye.ingestion.cache import FetchCache
from titan_eye.ingestion.sources.opensky import (
    OPENSKY_STATES_URL,
    OpenSkySource,
)
from titan_eye.ingestion.transport import FakeTransport, TransportResponse

T0 = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)


# ── RawArtifact ──────────────────────────────────────────────────────
def test_seal_computes_content_hash() -> None:
    payload = b'{"states": []}'
    art = RawArtifact.seal(
        source_id="opensky.states", domain=Domain.AERIAL,
        request_url=OPENSKY_STATES_URL, fetched_at=T0, payload=payload,
    )
    assert art.content_hash == content_hash_bytes(payload)
    assert art.epistemic_label is EpistemicLabel.OBSERVED
    assert art.domain is Domain.AERIAL


def test_artifact_is_frozen() -> None:
    art = RawArtifact.seal(
        source_id="s", domain=Domain.AERIAL, request_url="u", fetched_at=T0, payload=b"x",
    )
    try:
        art.content_hash = "tampered"  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("RawArtifact debería ser inmutable (frozen)")


# ── FetchCache ───────────────────────────────────────────────────────
def _artifact(payload: bytes, when: datetime) -> RawArtifact:
    return RawArtifact.seal(
        source_id="opensky.states", domain=Domain.AERIAL,
        request_url=OPENSKY_STATES_URL, fetched_at=when, payload=payload,
        epistemic_label=EpistemicLabel.OBSERVED, license_note="note",
    )


def test_cache_roundtrip_fresh(tmp_path) -> None:
    cache = FetchCache(tmp_path)
    art = _artifact(b'{"states":[]}', T0)
    cache.put(art, cache_key="k1")
    got = cache.get_fresh("k1", max_age_seconds=30, now=T0 + timedelta(seconds=5))
    assert got is not None
    assert got.content_hash == art.content_hash
    assert got.payload == art.payload
    assert got.license_note == "note"


def test_cache_miss_when_stale(tmp_path) -> None:
    cache = FetchCache(tmp_path)
    cache.put(_artifact(b"a", T0), cache_key="k1")
    assert cache.get_fresh("k1", max_age_seconds=10, now=T0 + timedelta(seconds=60)) is None


def test_cache_miss_unknown_key(tmp_path) -> None:
    cache = FetchCache(tmp_path)
    cache.put(_artifact(b"a", T0), cache_key="k1")
    assert cache.get_fresh("other", max_age_seconds=999, now=T0) is None


def test_cache_returns_latest_record(tmp_path) -> None:
    cache = FetchCache(tmp_path)
    cache.put(_artifact(b"old", T0), cache_key="k1")
    cache.put(_artifact(b"new", T0 + timedelta(seconds=5)), cache_key="k1")
    got = cache.get_fresh("k1", max_age_seconds=999, now=T0 + timedelta(seconds=6))
    assert got is not None and got.payload == b"new"


def test_cache_blob_is_idempotent(tmp_path) -> None:
    cache = FetchCache(tmp_path)
    art = _artifact(b"same", T0)
    cache.put(art, cache_key="k1")
    cache.put(art, cache_key="k2")  # mismos bytes -> un solo blob
    blobs = list((tmp_path / "blobs").rglob("*.bin"))
    assert len(blobs) == 1


# ── OpenSkySource ────────────────────────────────────────────────────
def _fake_transport() -> FakeTransport:
    ft = FakeTransport()
    ft.responses[OPENSKY_STATES_URL] = TransportResponse(
        url=OPENSKY_STATES_URL, status=200, body=opensky_payload(), media_type="application/json"
    )
    return ft


def test_source_seals_observed_artifact() -> None:
    src = OpenSkySource(transport=_fake_transport(), clock=FixedClock(T0))
    art = src.fetch_states()
    assert art.domain is Domain.AERIAL
    assert art.epistemic_label is EpistemicLabel.OBSERVED
    assert art.content_hash == content_hash_bytes(opensky_payload())
    assert "opensky" in art.license_note.lower()


def test_source_uses_cache_second_call(tmp_path) -> None:
    ft = _fake_transport()
    cache = FetchCache(tmp_path)
    src = OpenSkySource(transport=ft, cache=cache, clock=FixedClock(T0))
    src.fetch_states()
    src.fetch_states()  # debería venir de cache, sin segunda llamada de red
    assert len(ft.calls) == 1


def test_source_refetches_when_stale(tmp_path) -> None:
    ft = _fake_transport()
    cache = FetchCache(tmp_path)
    # Reloj que avanza más allá del max_age entre llamadas.
    src1 = OpenSkySource(transport=ft, cache=cache, clock=FixedClock(T0))
    src1.fetch_states(max_age_seconds=5)
    src2 = OpenSkySource(transport=ft, cache=cache, clock=FixedClock(T0 + timedelta(seconds=60)))
    src2.fetch_states(max_age_seconds=5)
    assert len(ft.calls) == 2
