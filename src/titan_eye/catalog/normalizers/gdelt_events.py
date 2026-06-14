"""Normalizador puro: RawArtifact (GDELT export.CSV.zip) -> list[ConflictEvent].

Determinista, sin red. Descomprime el ZIP de la base de eventos GDELT 2.0 (TSV de
61 columnas, sin cabecera) y conserva SOLO los eventos de **conflicto material**
(QuadClass=4: asalto, combate, coerción material, violencia masiva). Geolocaliza
por la ubicación del suceso (ActionGeo). Etiqueta `asserted` (afirmación de GDELT,
no verificada — ADR-0012/0003). El conteo de eventos es densidad de REPORTES, no
intensidad.
"""

from __future__ import annotations

import io
import zipfile
from datetime import date, datetime
from typing import Any

from titan_eye.catalog.surface import ConflictEvent, GeolocResolution
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.errors import NormalizationError
from titan_eye.ingestion.artifact import RawArtifact

GDELT_EVENTS_NORMALIZER_VERSION = "0.1.0"

# Índices de columna (GDELT 2.0 Event, 61 campos, 0-based).
_C_ID, _C_DAY, _C_ROOT, _C_QUAD = 0, 1, 28, 29
_C_GEOTYPE, _C_FULLNAME, _C_CC, _C_LAT, _C_LON = 51, 52, 53, 56, 57
_C_SOURCEURL = 60

# CAMEO EventRootCode -> etiqueta legible (solo conflicto).
_ROOT_LABELS = {
    "13": "Amenaza", "14": "Protesta", "15": "Despliegue de fuerza",
    "16": "Reducción de relaciones", "17": "Coerción", "18": "Asalto",
    "19": "Combate", "20": "Violencia masiva no convencional",
}

# ActionGeo_Type -> resolución de geolocalización declarada.
_GEO_RES = {
    "1": GeolocResolution.COUNTRY, "2": GeolocResolution.REGION,
    "3": GeolocResolution.CITY, "4": GeolocResolution.CITY,
    "5": GeolocResolution.REGION,
}


def normalize_gdelt_events(artifact: RawArtifact) -> list[ConflictEvent]:
    """ZIP de eventos GDELT -> list[ConflictEvent] de conflicto material (`asserted`)."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(artifact.payload))
    except zipfile.BadZipFile as exc:
        raise NormalizationError(
            "Payload GDELT events no es un ZIP válido", source_hash=artifact.content_hash
        ) from exc
    names = zf.namelist()
    if not names:
        raise NormalizationError(
            "ZIP de eventos GDELT vacío", source_hash=artifact.content_hash
        )
    text = zf.read(names[0]).decode("utf-8", "replace")

    out: list[ConflictEvent] = []
    for line in text.splitlines():
        cols = line.split("\t")
        if len(cols) < 58 or cols[_C_QUAD] != "4":  # solo conflicto material
            continue
        ev = _row_to_event(cols, artifact)
        if ev is not None:
            out.append(ev)
    return out


def _row_to_event(cols: list[str], artifact: RawArtifact) -> ConflictEvent | None:
    lat_s, lon_s = cols[_C_LAT].strip(), cols[_C_LON].strip()
    if not lat_s or not lon_s:
        return None  # sin coordenadas no se dibuja (P2: no se inventa)
    try:
        lat, lon = float(lat_s), float(lon_s)
        ev_date = _parse_day(cols[_C_DAY])
    except (ValueError, IndexError):
        return None
    root = cols[_C_ROOT].strip()
    source_url = cols[_C_SOURCEURL].strip() if len(cols) > _C_SOURCEURL else ""
    return ConflictEvent(
        event_id=f"gdelt-{cols[_C_ID].strip()}",
        event_date=ev_date,
        latitude=lat,
        longitude=lon,
        geoloc_resolution=_GEO_RES.get(cols[_C_GEOTYPE].strip(), GeolocResolution.COUNTRY),
        event_type=_ROOT_LABELS.get(root, f"CAMEO {root}"),
        location_name=cols[_C_FULLNAME].strip(),
        country=cols[_C_CC].strip() or None,
        source="GDELT 2.0 Events",
        source_url=source_url,
        notes="Evento extraído de prensa por GDELT · asserted · no verificado por Titan Eye",
        content_hash_source=artifact.content_hash,
        epistemic_label=EpistemicLabel.ASSERTED,
    )


def _parse_day(raw: Any) -> date:
    return datetime.strptime(str(raw).strip(), "%Y%m%d").date()
