"""Modelo de la capa OSINT: OsintItem (ADR-0020).

NO es un dominio físico: es información (noticias/RRSS geolocalizadas). Etiqueta
`asserted` — es lo que una FUENTE afirma, no lo que Titan Eye verifica. El
`source_tier` clasifica el TIPO de fuente (declarado por el operador), nunca la
veracidad del contenido. El sistema no puntúa credibilidad ni detecta
desinformación (ADR-0003): garantiza procedencia (quién lo dijo, cuándo, URL).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict

from titan_eye.core.epistemics import EpistemicLabel

OSINT_ITEM_SCHEMA_VERSION = "0.1.0"


class SourceTier(str, Enum):
    """Tipo de fuente (NO juicio de veracidad — ADR-0020)."""

    NEWS_AGENCY = "news_agency"     # Reuters, AP, AFP, EFE…
    GOVERNMENT = "government"        # comunicado oficial
    LOCAL_MEDIA = "local_media"     # medio local
    SOCIAL_MEDIA = "social_media"   # RRSS (menor validación)
    OTHER = "other"


class OsintItem(BaseModel):
    """Ítem OSINT geolocalizado (Normalized, capa OSINT, `asserted`)."""

    model_config = ConfigDict(frozen=True)

    item_id: str
    title: str
    latitude: float
    longitude: float
    source: str = ""                 # nombre de la fuente (p. ej. "Reuters")
    source_url: str = ""
    source_tier: SourceTier = SourceTier.OTHER
    published_at: datetime | None = None
    country: str | None = None
    summary: str = ""

    content_hash_source: str
    epistemic_label: EpistemicLabel = EpistemicLabel.ASSERTED
    schema_version: str = OSINT_ITEM_SCHEMA_VERSION
