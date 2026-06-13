"""Tests de la capa de referencia de instalaciones (ADR-0017): pública, estática, sin targeting."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.unit.fixtures_installations import installations_payload
from titan_eye.catalog.installations import (
    Installation,
    InstallationCategory,
    InstallationType,
)
from titan_eye.catalog.installations_repo import InstallationsRepository
from titan_eye.catalog.normalizers.installations import normalize_installations
from titan_eye.core.domains import Domain
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.errors import NormalizationError
from titan_eye.ingestion.artifact import RawArtifact
from titan_eye.orchestration.cli import run_ingest_installations
from titan_eye.orchestration.globe_payload import installations_to_entries

T0 = datetime(2026, 6, 12, 0, 0, 0, tzinfo=UTC)


def _artifact(payload: bytes | None = None) -> RawArtifact:
    return RawArtifact.seal(
        source_id="installations.reference", domain=Domain.REFERENCE,
        request_url="file://x", fetched_at=T0, payload=payload or installations_payload(),
        epistemic_label=EpistemicLabel.ASSERTED,
    )


def _items() -> list[Installation]:
    return normalize_installations(_artifact())


# ── Normalizador (asserted, referencia) ──────────────────────────────
def test_items_asserted_with_provenance() -> None:
    art = _artifact()
    items = normalize_installations(art)
    assert len(items) == 4
    assert all(i.epistemic_label is EpistemicLabel.ASSERTED for i in items)
    assert all(i.content_hash_source == art.content_hash for i in items)


def test_category_derivation() -> None:
    items = {i.installation_id: i for i in _items()}
    assert items["B1"].category is InstallationCategory.MILITARY          # air_base
    assert items["B2"].category is InstallationCategory.MILITARY          # naval_base (derivado)
    assert items["I1"].category is InstallationCategory.CRITICAL_INFRASTRUCTURE
    assert items["I2"].installation_type is InstallationType.OTHER        # sin tipo
    assert items["I2"].category is InstallationCategory.CRITICAL_INFRASTRUCTURE


def test_missing_field_raises() -> None:
    import json
    bad = [{"installation_id": "x", "name": "y", "latitude": 1.0}]   # falta longitude
    with pytest.raises(NormalizationError):
        normalize_installations(_artifact(json.dumps(bad).encode()))


# ── Globo ────────────────────────────────────────────────────────────
def test_globe_entries() -> None:
    entries = {e["id"]: e for e in installations_to_entries(_items())}
    assert entries["B1"]["category"] == "military" and entries["B1"]["type"] == "air_base"
    assert entries["I1"]["type"] == "nuclear_plant"


# ── Persistencia + integridad ────────────────────────────────────────
def test_repo_roundtrip_idempotent(tmp_path) -> None:
    repo = InstallationsRepository(tmp_path)
    assert repo.insert_snapshot(_items()) is True
    assert repo.insert_snapshot(_items()) is False
    assert repo.count() == 4


def test_integrity_clean(tmp_path) -> None:
    from titan_eye.ingestion.cache import FetchCache
    from titan_eye.provenance.integrity import verify_installations_integrity

    cache = FetchCache(tmp_path / "cache")
    art = _artifact()
    cache.put(art, cache_key="k")
    repo = InstallationsRepository(tmp_path / "ref")
    repo.insert_snapshot(normalize_installations(art))
    report = verify_installations_integrity(repo, cache)
    assert report.ok is True and report.n_states == 4


# ── CLI ──────────────────────────────────────────────────────────────
def test_cli_ingest_installations() -> None:
    summary, items = run_ingest_installations(artifact=_artifact())
    assert summary["layer"] == "installations"
    assert summary["epistemic_label"] == "asserted"
    assert summary["n_installations"] == 4
    assert summary["by_category"]["military"] == 2
    note = summary["note"].lower()
    assert "sin cómputo operacional" in note or "targeting" in note
    assert len(items) == 4


def test_cli_persist_then_verify_clean(tmp_path) -> None:
    from titan_eye.orchestration.cli import cli_entry_point

    f = tmp_path / "inst.json"
    f.write_bytes(installations_payload())
    root = tmp_path / "data"
    assert cli_entry_point(["ingest", "installations", "--file", str(f),
                            "--data-root", str(root), "--persist"]) == 0
    assert cli_entry_point(["verify-installations", "--data-root", str(root)]) == 0
