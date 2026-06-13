"""Ficha país de referencia: CountryProfile (ADR-0021).

Cifras de fuentes PÚBLICAS (SIPRI, IISS Military Balance, presupuestos oficiales),
con su año y fuente. Son estimaciones públicas, no datos de Titan Eye: etiqueta
`asserted`. NO hay ranking de poder ni "amenazas activas" (ADR-0003): solo las
cifras con su procedencia, para que el lector compare si quiere.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from titan_eye.core.epistemics import EpistemicLabel

COUNTRY_PROFILE_SCHEMA_VERSION = "0.1.0"


class CountryProfile(BaseModel):
    """Ficha país (referencia, `asserted`)."""

    model_config = ConfigDict(frozen=True)

    country: str
    iso_code: str | None = None
    region: str | None = None

    military_budget_usd: float | None = None
    budget_year: int | None = None
    active_personnel: int | None = None
    reserve_personnel: int | None = None
    alliances: list[str] = []

    source: str = ""
    source_url: str = ""
    notes: str = ""

    content_hash_source: str
    epistemic_label: EpistemicLabel = EpistemicLabel.ASSERTED
    schema_version: str = COUNTRY_PROFILE_SCHEMA_VERSION
