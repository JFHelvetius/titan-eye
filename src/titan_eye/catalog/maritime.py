"""Modelo Normalized del dominio marítimo: VesselPosition (ADR-0015).

Capa Normalized (ADR-0001/0006): inmutable, versionada, con FK por hash al Raw
(`content_hash_source`) y la etiqueta `observed` sellada (P9).

Honestidad (P2): el AIS es autodeclarado por el buque y trivialmente falsificable;
los buques de guerra apagan o falsean el AIS con frecuencia, y los submarinos
sumergidos no transmiten. `last_contact_age_s` mide la antigüedad del mensaje. La
`vessel_type` es la clase DECLARADA por el dato público, descriptiva, nunca un
juicio de amenaza (ADR-0003).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict

from titan_eye.core.epistemics import EpistemicLabel

VESSEL_POSITION_SCHEMA_VERSION = "0.1.0"


class VesselType(str, Enum):
    """Clase de buque declarada (descriptiva, no acusatoria — ADR-0003)."""

    CARRIER = "carrier"          # portaaviones
    DESTROYER = "destroyer"      # destructor
    FRIGATE = "frigate"          # fragata
    SUBMARINE = "submarine"      # submarino (no transmite AIS sumergido)
    AMPHIBIOUS = "amphibious"    # buque anfibio
    PATROL = "patrol"            # patrullero
    AUXILIARY = "auxiliary"      # apoyo / logística / cisterna
    OTHER = "other"


class VesselPosition(BaseModel):
    """Posición instantánea de un buque (Normalized, dominio marítimo)."""

    model_config = ConfigDict(frozen=True)

    mmsi: str                       # identidad AIS (Maritime Mobile Service Identity)
    name: str | None = None
    vessel_type: VesselType = VesselType.OTHER
    flag: str | None = None         # país de bandera declarado

    latitude: float
    longitude: float
    course_deg: float | None = None        # rumbo sobre el fondo
    heading_deg: float | None = None       # proa
    speed_knots: float | None = None
    nav_status: str | None = None          # p. ej. "under way", "at anchor"

    # Calidad / incertidumbre (P2)
    last_contact: datetime
    last_contact_age_s: float | None = None

    # Procedencia y versionado
    content_hash_source: str
    snapshot_time: datetime
    epistemic_label: EpistemicLabel = EpistemicLabel.OBSERVED
    schema_version: str = VESSEL_POSITION_SCHEMA_VERSION
