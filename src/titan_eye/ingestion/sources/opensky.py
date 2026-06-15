"""Adaptador de la fuente OpenSky Network (dominio aéreo, ADS-B).

Implementa el contrato de procedencia de ADR-0002 para el dominio aéreo. NO
interpreta el payload: adquiere el JSON de estados de OpenSky y lo sella como
RawArtifact con etiqueta `observed` (la posición la declara la propia aeronave).

Política cache-first (ADR-0002): las posiciones ADS-B caducan en segundos; el
`max_age` por defecto es deliberadamente corto. La cuenta de OpenSky (token) es
opcional y solo amplía rate/cobertura: el tier anónimo es camino válido (P3).

Referencia: OpenSky REST API, endpoint `/api/states/all`.
"""

from __future__ import annotations

from titan_eye.core.domains import Domain
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.errors import TransportError
from titan_eye.core.timebase import Clock, SystemClock
from titan_eye.ingestion.artifact import RawArtifact
from titan_eye.ingestion.cache import FetchCache
from titan_eye.ingestion.transport import Transport, UrllibTransport

OPENSKY_STATES_URL = "https://opensky-network.org/api/states/all"
OPENSKY_SOURCE_ID = "opensky.states"
# OAuth2 (client credentials). Una cuenta GRATUITA de OpenSky sube mucho el límite
# por IP — necesario en hosts de IP compartida como Streamlit Cloud (P3/P7).
OPENSKY_TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network/"
    "protocol/openid-connect/token"
)
# Términos de uso: OpenSky Network es de uso no comercial / investigación con
# atribución. Se propaga como dato para que el output lo respete (ADR-0002).
OPENSKY_LICENSE_NOTE = (
    "OpenSky Network — uso no comercial / investigación, con atribución. "
    "https://opensky-network.org/about/terms-of-use"
)
# Posiciones ADS-B de altísima cadencia: ventana de frescura corta.
DEFAULT_MAX_AGE_SECONDS = 15.0


class OpenSkySource:
    """Fuente OpenSky con transporte, cache y reloj inyectables."""

    def __init__(
        self,
        *,
        transport: Transport | None = None,
        cache: FetchCache | None = None,
        clock: Clock | None = None,
        client_id: str = "",
        client_secret: str = "",
    ) -> None:
        self.transport = transport or UrllibTransport()
        self.cache = cache
        self.clock = clock or SystemClock()
        self.client_id = client_id
        self.client_secret = client_secret
        self._token = ""
        self._token_expiry = 0.0

    def _auth_headers(self) -> dict[str, str]:
        """Cabecera Bearer si hay credenciales; vacío si es anónimo.

        Sin red en modo anónimo (no rompe los tests con FakeTransport)."""
        if not (self.client_id and self.client_secret):
            return {}
        return {"Authorization": f"Bearer {self._access_token()}"}

    def _access_token(self) -> str:
        import json
        import time
        import urllib.parse
        import urllib.request

        if self._token and time.time() < self._token_expiry - 30:
            return self._token
        data = urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }).encode("ascii")
        req = urllib.request.Request(
            OPENSKY_TOKEN_URL, data=data, method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "User-Agent": "TitanEye/0.1 (+github.com/JFHelvetius/titan-eye)"},
        )
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                doc = json.loads(resp.read())
        except Exception as exc:  # se traduce a un error de transporte claro
            raise TransportError(
                "OpenSky: no se pudo obtener token OAuth2 (¿credenciales válidas?): "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        self._token = str(doc.get("access_token", ""))
        self._token_expiry = time.time() + float(doc.get("expires_in", 1800))
        if not self._token:
            raise TransportError("OpenSky: respuesta de token sin access_token")
        return self._token

    def fetch_states(
        self,
        *,
        bbox: tuple[float, float, float, float] | None = None,
        max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS,
    ) -> RawArtifact:
        """Adquiere los estados ADS-B actuales y los sella como RawArtifact.

        bbox = (lat_min, lat_max, lon_min, lon_max) para acotar la región.
        Devuelve un RawArtifact `observed`. Reutiliza la cache si hay una
        adquisición fresca del mismo request.
        """
        params = _bbox_params(bbox)
        cache_key = _cache_key(params)
        now = self.clock.now()

        if self.cache is not None:
            cached = self.cache.get_fresh(
                cache_key, max_age_seconds=max_age_seconds, now=now
            )
            if cached is not None:
                return cached

        resp = self.transport.get(OPENSKY_STATES_URL, params=params, headers=self._auth_headers())
        artifact = RawArtifact.seal(
            source_id=OPENSKY_SOURCE_ID,
            domain=Domain.AERIAL,
            request_url=OPENSKY_STATES_URL,
            request_params=params,
            fetched_at=now,
            payload=resp.body,
            media_type=resp.media_type,
            epistemic_label=EpistemicLabel.OBSERVED,
            license_note=OPENSKY_LICENSE_NOTE,
        )
        if self.cache is not None:
            self.cache.put(artifact, cache_key=cache_key)
        return artifact


def _bbox_params(bbox: tuple[float, float, float, float] | None) -> dict[str, str]:
    if bbox is None:
        return {}
    lamin, lamax, lomin, lomax = bbox
    return {
        "lamin": _fmt(lamin), "lamax": _fmt(lamax),
        "lomin": _fmt(lomin), "lomax": _fmt(lomax),
    }


def _fmt(x: float) -> str:
    # Formato estable para que el cache_key sea determinista.
    return f"{x:.6f}"


def _cache_key(params: dict[str, str]) -> str:
    import json

    body = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return f"{OPENSKY_SOURCE_ID}:{body}"
