"""Modelo Normalized del dominio superficie: ConflictEvent (ADR-0012).

Un evento de conflicto es una **afirmación de un tercero** (`asserted`, P9): lo
reportó ACLED/GDELT/OSINT, no lo verificó Titan Eye. La `geoloc_resolution`
declara cuán precisa es su ubicación; el render la traduce a un halo (ADR-0004),
nunca a un punto nítido sobre una posición aproximada (P2).

Las víctimas reportadas (`reported_fatalities`) son un ATRIBUTO descriptivo del
evento. NUNCA se usan como peso del mapa de calor: el mapa mide densidad de
reportes, no intensidad (ADR-0003).
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict

from titan_eye.core.epistemics import EpistemicLabel

CONFLICT_EVENT_SCHEMA_VERSION = "0.1.0"


class GeolocResolution(str, Enum):
    """Resolución declarada de la geolocalización del evento (P2)."""

    EXACT = "exact"       # coordenadas precisas
    CITY = "city"         # ciudad / municipio
    REGION = "region"     # provincia / admin1
    COUNTRY = "country"   # solo país


class ConflictEvent(BaseModel):
    """Evento de conflicto reportado (Normalized, dominio superficie)."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    event_date: date
    latitude: float
    longitude: float
    geoloc_resolution: GeolocResolution = GeolocResolution.CITY

    event_type: str = ""
    location_name: str = ""
    # Atributo descriptivo del reporte. NO es peso del mapa de calor (ADR-0003).
    reported_fatalities: int = 0

    # Procedencia del reporte
    source: str = ""
    source_url: str = ""
    notes: str = ""

    content_hash_source: str
    epistemic_label: EpistemicLabel = EpistemicLabel.ASSERTED
    schema_version: str = CONFLICT_EVENT_SCHEMA_VERSION
