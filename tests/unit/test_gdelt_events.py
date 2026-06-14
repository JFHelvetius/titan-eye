"""Tests de la base de eventos GDELT 2.0 (dominio superficie, sin clave)."""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, date, datetime

import pytest

from titan_eye.catalog.normalizers.gdelt_events import normalize_gdelt_events
from titan_eye.catalog.surface import GeolocResolution
from titan_eye.core.domains import Domain
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.errors import NormalizationError
from titan_eye.ingestion.artifact import RawArtifact
from titan_eye.ingestion.sources.gdelt_events import recent_timestamps

T0 = datetime(2026, 6, 14, 8, 0, 0, tzinfo=UTC)


def _row(gid: str, root: str, quad: str, geotype: str, lat: str, lon: str,
         day: str = "20260614", name: str = "Kyiv, Ukraine", cc: str = "UP") -> str:
    cols = [""] * 61
    cols[0], cols[1], cols[28], cols[29] = gid, day, root, quad
    cols[51], cols[52], cols[53], cols[56], cols[57] = geotype, name, cc, lat, lon
    cols[60] = f"https://news/{gid}"
    return "\t".join(cols)


def _zip_bytes(rows: list[str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("20260614080000.export.CSV", "\n".join(rows))
    return buf.getvalue()


def _artifact(payload: bytes) -> RawArtifact:
    return RawArtifact.seal(
        source_id="gdelt.events", domain=Domain.SURFACE,
        request_url="http://data.gdeltproject.org/x.zip", fetched_at=T0, payload=payload,
        epistemic_label=EpistemicLabel.ASSERTED,
    )


_ROWS = [
    _row("1", "19", "4", "4", "50.45", "30.52"),   # combate, material -> SÍ
    _row("2", "20", "4", "1", "33.0", "44.0"),      # violencia masiva, país -> SÍ
    _row("3", "01", "1", "4", "40.0", "-3.0"),      # cooperación verbal -> NO (quad!=4)
    _row("4", "19", "4", "4", "", ""),               # sin coords -> NO
]


def test_keeps_only_material_conflict_with_coords() -> None:
    events = normalize_gdelt_events(_artifact(_zip_bytes(_ROWS)))
    ids = {e.event_id for e in events}
    assert ids == {"gdelt-1", "gdelt-2"}  # 3 (verbal) y 4 (sin coords) fuera


def test_event_fields_and_labels() -> None:
    events = normalize_gdelt_events(_artifact(_zip_bytes(_ROWS)))
    e1 = next(e for e in events if e.event_id == "gdelt-1")
    assert e1.event_type == "Combate"
    assert e1.event_date == date(2026, 6, 14)
    assert e1.geoloc_resolution is GeolocResolution.CITY
    assert e1.epistemic_label is EpistemicLabel.ASSERTED
    assert (e1.latitude, e1.longitude) == (50.45, 30.52)


def test_country_resolution_for_country_geotype() -> None:
    events = normalize_gdelt_events(_artifact(_zip_bytes(_ROWS)))
    e2 = next(e for e in events if e.event_id == "gdelt-2")
    assert e2.geoloc_resolution is GeolocResolution.COUNTRY


def test_provenance_links_to_artifact() -> None:
    art = _artifact(_zip_bytes(_ROWS))
    events = normalize_gdelt_events(art)
    assert all(e.content_hash_source == art.content_hash for e in events)


def test_bad_zip_raises() -> None:
    with pytest.raises(NormalizationError):
        normalize_gdelt_events(_artifact(b"not a zip"))


def test_recent_timestamps_steps_back_15min() -> None:
    ts = recent_timestamps("20260614080000", 3)
    assert ts == ["20260614080000", "20260614074500", "20260614073000"]
