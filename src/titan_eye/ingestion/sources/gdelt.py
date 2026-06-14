"""Adaptador de la fuente GDELT (noticias geolocalizadas, dominio OSINT).

GDELT (Global Database of Events, Language, and Tone) indexa la prensa mundial en
near-real-time. Su DOC 2.0 API es **pública y sin clave** (ADR-0002/P7). Titan Eye
adquiere el listado de artículos que casan una consulta y lo sella como
RawArtifact `asserted` (es una afirmación de terceros: la prensa, no un dato
verificado por Titan Eye — ADR-0020).

Referencia: GDELT DOC 2.0 API, `https://api.gdeltproject.org/api/v2/doc/doc`.
"""

from __future__ import annotations

from titan_eye.core.domains import Domain
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.timebase import Clock, SystemClock
from titan_eye.ingestion.artifact import RawArtifact
from titan_eye.ingestion.cache import FetchCache
from titan_eye.ingestion.transport import Transport, UrllibTransport

GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_SOURCE_ID = "gdelt.doc"
GDELT_LICENSE_NOTE = (
    "GDELT Project — datos de noticias públicos, sin clave, con atribución. "
    "https://www.gdeltproject.org/"
)
# Consulta militar/conflicto por defecto (sintaxis DOC API). Términos separados por
# espacio = AND implícito; conjunto sobrio que casa mucha prensa de defensa.
DEFAULT_QUERY = "military conflict"
# La prensa se actualiza por minutos; ventana de frescura corta.
DEFAULT_MAX_AGE_SECONDS = 300.0


class GdeltSource:
    """Fuente GDELT DOC con transporte, cache y reloj inyectables."""

    def __init__(
        self,
        *,
        transport: Transport | None = None,
        cache: FetchCache | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.transport = transport or UrllibTransport()
        self.cache = cache
        self.clock = clock or SystemClock()

    def fetch_doc(
        self,
        *,
        query: str = DEFAULT_QUERY,
        timespan: str = "24h",
        max_records: int = 250,
        max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS,
        timeout: float = 8.0,
    ) -> RawArtifact:
        """Adquiere el listado de artículos GDELT y lo sella como RawArtifact.

        `timeout` corto a propósito: la DOC API limita por IP (429) y si está
        saturada conviene rendirse rápido (es una capa secundaria)."""
        params = {
            "query": query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": str(max_records),
            "timespan": timespan,
            "sort": "datedesc",
        }
        cache_key = _cache_key(params)
        now = self.clock.now()
        if self.cache is not None:
            cached = self.cache.get_fresh(cache_key, max_age_seconds=max_age_seconds, now=now)
            if cached is not None:
                return cached
        resp = self.transport.get(GDELT_DOC_URL, params=params, timeout=timeout)
        artifact = RawArtifact.seal(
            source_id=GDELT_SOURCE_ID,
            domain=Domain.OSINT,
            request_url=GDELT_DOC_URL,
            request_params=params,
            fetched_at=now,
            payload=resp.body,
            media_type=resp.media_type,
            epistemic_label=EpistemicLabel.ASSERTED,
            license_note=GDELT_LICENSE_NOTE,
        )
        if self.cache is not None:
            self.cache.put(artifact, cache_key=cache_key)
        return artifact


def _cache_key(params: dict[str, str]) -> str:
    import json

    return f"{GDELT_SOURCE_ID}:{json.dumps(params, sort_keys=True, separators=(',', ':'))}"
