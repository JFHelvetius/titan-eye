"""Modelo Normalized del dominio aéreo: AircraftState.

Es la capa Normalized (ADR-0001/0006): inmutable, versionada, con FK por hash al
RawArtifact de origen (`content_hash_source`, ADR-0005) y con la etiqueta
epistémica sellada (`observed`, P9). Un AircraftState es un estado instantáneo de
una aeronave tal y como lo reportó su transpondedor ADS-B.

La incertidumbre (P2) es de primera clase: `last_contact_age_s` mide la
antigüedad del último mensaje y `position_source` distingue ADS-B de MLAT/otros.
Una posición antigua o de una fuente menos precisa NO se presenta igual que una
reciente y directa (el render lo refleja, ADR-0004).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from titan_eye.core.epistemics import EpistemicLabel

AIRCRAFT_STATE_SCHEMA_VERSION = "0.1.0"

# Tabla de `position_source` de OpenSky (índice 16 del vector de estado).
POSITION_SOURCE = {0: "ADS-B", 1: "ASTERIX", 2: "MLAT", 3: "FLARM"}


class AircraftState(BaseModel):
    """Estado instantáneo de una aeronave (Normalized, dominio aéreo)."""

    model_config = ConfigDict(frozen=True)

    # Identidad de la aeronave
    icao24: str
    callsign: str | None = None
    origin_country: str | None = None

    # Geometría (None si OpenSky no reporta posición en este ciclo)
    longitude: float | None = None
    latitude: float | None = None
    baro_altitude_m: float | None = None
    geo_altitude_m: float | None = None
    on_ground: bool = False

    # Cinemática
    velocity_ms: float | None = None
    true_track_deg: float | None = None
    vertical_rate_ms: float | None = None

    # Calidad / incertidumbre (P2)
    time_position: datetime | None = None
    last_contact: datetime
    last_contact_age_s: float | None = None
    position_source: str = "ADS-B"
    squawk: str | None = None
    spi: bool = False

    # Procedencia y versionado (ADR-0005/0006)
    content_hash_source: str
    snapshot_time: datetime
    epistemic_label: EpistemicLabel = EpistemicLabel.OBSERVED
    schema_version: str = AIRCRAFT_STATE_SCHEMA_VERSION

    @property
    def has_position(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    @property
    def altitude_km(self) -> float | None:
        alt = self.geo_altitude_m if self.geo_altitude_m is not None else self.baro_altitude_m
        return None if alt is None else alt / 1000.0
