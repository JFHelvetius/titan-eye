"""Adaptador de la base de EVENTOS de GDELT 2.0 (dominio superficie).

A diferencia de GDELT DOC (noticias geolocalizadas por país de la fuente), la base
de Eventos trae la **ubicación del propio suceso** (ActionGeo_Lat/Long) extraída por
GDELT del texto. Es **pública y sin clave** (P3/P7). Se publica un fichero cada 15
min (`export.CSV.zip`). Titan Eye sella cada fichero como RawArtifact `asserted`
(es la afirmación de GDELT, no verificada por Titan Eye — ADR-0012/0003).

Referencia: GDELT 2.0 Event Database, http://data.gdeltproject.org/gdeltv2/
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from titan_eye.core.domains import Domain
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.timebase import Clock, SystemClock
from titan_eye.ingestion.artifact import RawArtifact
from titan_eye.ingestion.cache import FetchCache
from titan_eye.ingestion.transport import Transport, UrllibTransport

GDELT_GGV2_BASE = "http://data.gdeltproject.org/gdeltv2/"
GDELT_LASTUPDATE_URL = GDELT_GGV2_BASE + "lastupdate.txt"
GDELT_EVENTS_SOURCE_ID = "gdelt.events"
GDELT_EVENTS_LICENSE_NOTE = (
    "GDELT Project — base de eventos pública, sin clave, con atribución. "
    "https://www.gdeltproject.org/"
)
DEFAULT_MAX_AGE_SECONDS = 900.0  # un fichero por cada 15 min


class GdeltEventsSource:
    """Fuente de la base de eventos GDELT 2.0 (transporte/cache/reloj inyectables)."""

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

    def resolve_latest_timestamp(self) -> str:
        """Lee lastupdate.txt y devuelve el timestamp (YYYYMMDDHHMMSS) del último export."""
        resp = self.transport.get(GDELT_LASTUPDATE_URL)
        text = resp.body.decode("utf-8", "replace")
        for line in text.splitlines():
            parts = line.split()
            if parts and parts[-1].endswith(".export.CSV.zip"):
                fname = parts[-1].rsplit("/", 1)[-1]
                return fname.split(".")[0]
        raise ValueError("lastupdate.txt sin línea de export reconocible")

    def fetch_export(self, timestamp: str, *, max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS
                     ) -> RawArtifact:
        """Adquiere el `export.CSV.zip` de un timestamp y lo sella (payload = zip)."""
        url = f"{GDELT_GGV2_BASE}{timestamp}.export.CSV.zip"
        cache_key = f"{GDELT_EVENTS_SOURCE_ID}:{timestamp}"
        now = self.clock.now()
        if self.cache is not None:
            cached = self.cache.get_fresh(cache_key, max_age_seconds=max_age_seconds, now=now)
            if cached is not None:
                return cached
        resp = self.transport.get(url)
        artifact = RawArtifact.seal(
            source_id=GDELT_EVENTS_SOURCE_ID,
            domain=Domain.SURFACE,
            request_url=url,
            fetched_at=now,
            payload=resp.body,
            media_type=resp.media_type,
            epistemic_label=EpistemicLabel.ASSERTED,
            license_note=GDELT_EVENTS_LICENSE_NOTE,
        )
        if self.cache is not None:
            self.cache.put(artifact, cache_key=cache_key)
        return artifact


def recent_timestamps(latest: str, n: int) -> list[str]:
    """Devuelve `n` timestamps de 15 min hacia atrás desde `latest` (incluido)."""
    base = datetime.strptime(latest, "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    return [(base - timedelta(minutes=15 * i)).strftime("%Y%m%d%H%M%S") for i in range(n)]
