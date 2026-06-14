"""Adaptador de OpenStreetMap vía Overpass API (instalaciones militares).

Overpass es la API de consulta de OpenStreetMap: **pública y sin clave** (P3/P7).
Titan Eye consulta las instalaciones militares mapeadas (bases navales, aeródromos
militares, cuarteles…) y las sella como RawArtifact `asserted` para la capa de
referencia (ADR-0017): geografía pública, NO actividad. Puede estar incompleta o
desactualizada (P2) — OSM lo mantiene la comunidad y los emplazamientos sensibles
a veces no están mapeados. Ausencia ≠ inexistencia.

Referencia: Overpass API, `https://overpass-api.de/api/interpreter`.
"""

from __future__ import annotations

from titan_eye.core.domains import Domain
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.timebase import Clock, SystemClock
from titan_eye.ingestion.artifact import RawArtifact
from titan_eye.ingestion.cache import FetchCache
from titan_eye.ingestion.transport import Transport, UrllibTransport

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# Mirrors públicos: si el principal está saturado (400/429/timeout), se prueba el
# siguiente. El orden pone primero el que suele estar más libre.
OVERPASS_MIRRORS = (
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
)
OVERPASS_SOURCE_ID = "osm.overpass"
OVERPASS_LICENSE_NOTE = (
    "© OpenStreetMap contributors (ODbL) vía Overpass API — datos públicos, "
    "con atribución. https://www.openstreetmap.org/copyright"
)
# Geografía estática: ventana de frescura larga (la capa cambia muy despacio).
DEFAULT_MAX_AGE_SECONDS = 24 * 3600.0

# Consulta Overpass QL: instalaciones militares CON NOMBRE, en todo el mundo,
# acotada en cantidad para no saturar ni el servidor ni el globo. `out center`
# da un punto representativo para ways/relations (polígonos). Se limita a los
# tipos más distintivos y menos numerosos: un barrido global de `military=*`
# satura la instancia pública (la rechaza con 400/timeout).
def _query(max_elements: int) -> str:
    return (
        "[out:json][timeout:180];"
        "("
        'nwr["military"="naval_base"]["name"];'
        'nwr["military"="airfield"]["name"];'
        'nwr["military"="barracks"]["name"];'
        ")"
        f"out center {max_elements};"
    )


class OverpassSource:
    """Fuente Overpass/OSM con transporte, cache y reloj inyectables."""

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

    def fetch_military(
        self,
        *,
        max_elements: int = 1500,
        max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS,
        endpoints: tuple[str, ...] = OVERPASS_MIRRORS,
    ) -> RawArtifact:
        """Adquiere las instalaciones militares de OSM y las sella como RawArtifact.

        Prueba los mirrors en orden; si uno falla (saturado/timeout), pasa al
        siguiente. Geografía estática → cache largo."""
        params = {"data": _query(max_elements)}
        cache_key = f"{OVERPASS_SOURCE_ID}:military:{max_elements}"
        now = self.clock.now()
        if self.cache is not None:
            cached = self.cache.get_fresh(cache_key, max_age_seconds=max_age_seconds, now=now)
            if cached is not None:
                return cached

        last_exc: Exception | None = None
        for endpoint in endpoints:
            try:
                resp = self.transport.get(endpoint, params=params, timeout=185.0)
            except Exception as exc:  # mirror saturado → probar el siguiente
                last_exc = exc
                continue
            artifact = RawArtifact.seal(
                source_id=OVERPASS_SOURCE_ID,
                domain=Domain.REFERENCE,
                request_url=endpoint,
                request_params=params,
                fetched_at=now,
                payload=resp.body,
                media_type=resp.media_type,
                epistemic_label=EpistemicLabel.ASSERTED,
                license_note=OVERPASS_LICENSE_NOTE,
            )
            if self.cache is not None:
                self.cache.put(artifact, cache_key=cache_key)
            return artifact
        raise last_exc if last_exc is not None else RuntimeError("Overpass: sin endpoints")
