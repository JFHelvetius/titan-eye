"""Tests del dominio superficie: evento, KDE, globo, persistencia, integridad, CLI."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from tests.unit.fixtures_surface import CONFLICT_EVENTS, events_payload
from titan_eye.analytics.surface.heatmap import (
    KDE_KERNEL_NAME,
    _haversine_km,
    compute_heatmap,
)
from titan_eye.catalog.conflict_events_repo import ConflictEventsRepository
from titan_eye.catalog.normalizers.conflict_events import normalize_conflict_events
from titan_eye.catalog.surface import ConflictEvent, GeolocResolution
from titan_eye.core.domains import Domain
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.errors import NormalizationError
from titan_eye.ingestion.artifact import RawArtifact
from titan_eye.orchestration.cli import run_ingest_surface
from titan_eye.orchestration.globe_payload import (
    conflict_events_to_entries,
    heatmap_to_points,
)

T0 = datetime(2026, 6, 12, 0, 0, 0, tzinfo=UTC)


def _artifact(payload: bytes | None = None) -> RawArtifact:
    return RawArtifact.seal(
        source_id="conflict.events", domain=Domain.SURFACE,
        request_url="file://x", fetched_at=T0, payload=payload or events_payload(),
        epistemic_label=EpistemicLabel.ASSERTED,
    )


def _events() -> list[ConflictEvent]:
    return normalize_conflict_events(_artifact())


# ── Normalizador (asserted) ──────────────────────────────────────────
def test_events_are_asserted_with_provenance() -> None:
    art = _artifact()
    events = normalize_conflict_events(art)
    assert len(events) == 6
    assert all(e.epistemic_label is EpistemicLabel.ASSERTED for e in events)
    assert all(e.content_hash_source == art.content_hash for e in events)


def test_geoloc_resolution_mapped() -> None:
    events = {e.event_id: e for e in _events()}
    assert events["E2"].geoloc_resolution is GeolocResolution.EXACT   # geo_precision=1
    assert events["E3"].geoloc_resolution is GeolocResolution.REGION
    assert events["E5"].geoloc_resolution is GeolocResolution.EXACT
    assert events["E1"].event_date == date(2026, 6, 10)


def test_missing_field_raises() -> None:
    import json
    bad = [dict(CONFLICT_EVENTS[0])]
    del bad[0]["latitude"]
    with pytest.raises(NormalizationError):
        normalize_conflict_events(_artifact(json.dumps(bad).encode()))


# ── KDE heatmap ──────────────────────────────────────────────────────
def test_haversine_known_distance() -> None:
    # ~111 km por grado de latitud cerca del ecuador
    assert _haversine_km(0.0, 0.0, 1.0, 0.0) == pytest.approx(111.2, abs=1.0)


def test_heatmap_peaks_near_clusters() -> None:
    hm = compute_heatmap(_events(), bandwidth_km=40.0, grid_deg=0.25)
    assert hm.kernel_name == KDE_KERNEL_NAME
    assert hm.n_events == 6
    assert hm.points  # hay celdas por encima del umbral
    # El máximo (weight==1) debe caer cerca del clúster denso A (~48.0, 37.6)
    peak = max(hm.points, key=lambda p: p[2])
    assert peak[2] == pytest.approx(1.0, abs=1e-6)
    assert abs(peak[1] - 48.0) < 1.5 and abs(peak[0] - 37.6) < 1.5


def test_heatmap_weights_normalized() -> None:
    hm = compute_heatmap(_events(), bandwidth_km=50.0)
    assert all(0.0 < p[2] <= 1.0 for p in hm.points)


def test_heatmap_semantics_declares_reports() -> None:
    hm = compute_heatmap(_events())
    assert "REPORTADOS" in hm.semantics_note
    assert "no intensidad" in hm.semantics_note.lower()


def test_heatmap_bandwidth_affects_spread() -> None:
    narrow = compute_heatmap(_events(), bandwidth_km=15.0, grid_deg=0.25)
    wide = compute_heatmap(_events(), bandwidth_km=120.0, grid_deg=0.25)
    # Mayor bandwidth difumina más -> más celdas por encima del umbral.
    assert len(wide.points) > len(narrow.points)


def test_heatmap_empty_events() -> None:
    hm = compute_heatmap([], bandwidth_km=50.0)
    assert hm.points == [] and hm.n_events == 0


# ── Globo ────────────────────────────────────────────────────────────
def test_surface_globe_entries_carry_geoloc() -> None:
    entries = conflict_events_to_entries(_events())
    assert len(entries) == 6
    e1 = next(x for x in entries if x["id"] == "E1")
    assert e1["geoloc_res"] == "city"
    assert "date" in e1 and "event_type" in e1


def test_heatmap_globe_points() -> None:
    hm = compute_heatmap(_events(), bandwidth_km=40.0)
    pts = heatmap_to_points(hm)
    assert all(set(p) == {"lon", "lat", "weight"} for p in pts)


# ── Persistencia + CLI ───────────────────────────────────────────────
def test_repo_roundtrip_idempotent(tmp_path) -> None:
    repo = ConflictEventsRepository(tmp_path)
    assert repo.insert_snapshot(_events()) is True
    assert repo.insert_snapshot(_events()) is False
    assert repo.count() == 6
    back = {e.event_id: e for e in repo.iter_all()}
    assert back["E5"].geoloc_resolution is GeolocResolution.EXACT


def test_cli_ingest_surface_is_asserted() -> None:
    summary, events = run_ingest_surface(artifact=_artifact())
    assert summary["domain"] == "surface"
    assert summary["epistemic_label"] == "asserted"
    assert summary["n_events"] == 6
    assert "AFIRMADOS" in summary["note"]
    assert len(events) == 6


def test_surface_integrity_clean(tmp_path) -> None:
    from titan_eye.ingestion.cache import FetchCache
    from titan_eye.provenance.integrity import verify_surface_integrity

    cache = FetchCache(tmp_path / "cache")
    art = _artifact()
    cache.put(art, cache_key="k")
    repo = ConflictEventsRepository(tmp_path / "norm")
    repo.insert_snapshot(normalize_conflict_events(art))
    report = verify_surface_integrity(repo, cache)
    assert report.ok is True
    assert report.n_states == 6 and report.n_source_hashes == 1
