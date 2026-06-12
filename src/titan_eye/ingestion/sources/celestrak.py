"""Adaptador de la fuente CelesTrak (dominio orbital, TLE/GP).

Implementa el contrato de procedencia de ADR-0002 para el dominio orbital.
Adquiere texto TLE por GROUP (p. ej. `stations`, `active`, grupos públicos) o por
CATNR, y lo sella como RawArtifact `observed`. Reusa transporte/cache/reloj de
ADR-0009. CelesTrak no requiere autenticación (P3/P7).

Referencia: CelesTrak GP API, `https://celestrak.org/NORAD/elements/gp.php`.
"""

from __future__ import annotations

from titan_eye.core.domains import Domain
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.timebase import Clock, SystemClock
from titan_eye.ingestion.artifact import RawArtifact
from titan_eye.ingestion.cache import FetchCache
from titan_eye.ingestion.transport import Transport, UrllibTransport

CELESTRAK_GP_URL = "https://celestrak.org/NORAD/elements/gp.php"
CELESTRAK_SOURCE_ID = "celestrak.gp"
CELESTRAK_LICENSE_NOTE = (
    "CelesTrak (T.S. Kelso) — datos GP/TLE públicos, con atribución. "
    "https://celestrak.org"
)
# Un TLE cambia, como mucho, varias veces al día: ventana de frescura amplia.
DEFAULT_MAX_AGE_SECONDS = 6 * 3600.0


class CelesTrakSource:
    """Fuente CelesTrak con transporte, cache y reloj inyectables."""

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

    def fetch_group(
        self, group: str, *, max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS
    ) -> RawArtifact:
        """Adquiere el TLE de un GROUP de CelesTrak (formato TLE)."""
        return self._fetch({"GROUP": group, "FORMAT": "tle"}, max_age_seconds)

    def fetch_catnr(
        self, catnr: int, *, max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS
    ) -> RawArtifact:
        """Adquiere el TLE de un satélite por número de catálogo NORAD."""
        return self._fetch({"CATNR": str(catnr), "FORMAT": "tle"}, max_age_seconds)

    def _fetch(self, params: dict[str, str], max_age_seconds: float) -> RawArtifact:
        cache_key = _cache_key(params)
        now = self.clock.now()
        if self.cache is not None:
            cached = self.cache.get_fresh(cache_key, max_age_seconds=max_age_seconds, now=now)
            if cached is not None:
                return cached
        resp = self.transport.get(CELESTRAK_GP_URL, params=params)
        artifact = RawArtifact.seal(
            source_id=CELESTRAK_SOURCE_ID,
            domain=Domain.ORBITAL,
            request_url=CELESTRAK_GP_URL,
            request_params=params,
            fetched_at=now,
            payload=resp.body,
            media_type=resp.media_type,
            epistemic_label=EpistemicLabel.OBSERVED,
            license_note=CELESTRAK_LICENSE_NOTE,
        )
        if self.cache is not None:
            self.cache.put(artifact, cache_key=cache_key)
        return artifact


def _cache_key(params: dict[str, str]) -> str:
    import json

    return f"{CELESTRAK_SOURCE_ID}:{json.dumps(params, sort_keys=True, separators=(',', ':'))}"
