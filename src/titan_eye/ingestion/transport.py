"""Transporte HTTP inyectable.

El `Transport` es un Protocol para que las fuentes se testeen sin red: en tests
se inyecta un `FakeTransport` con respuestas pre-registradas (cualquier escape a
red se vuelve visible inmediatamente). En producción, `UrllibTransport` usa solo
stdlib — cero dependencias nuevas (P3).
"""

from __future__ import annotations

import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol

from titan_eye.core.errors import TransportError

# Muchos servicios públicos (CelesTrak entre ellos) ralentizan o rechazan a
# clientes sin User-Agent. Identificarse honestamente evita timeouts espurios.
_DEFAULT_USER_AGENT = (
    "TitanEye/0.1 (+https://github.com/JFHelvetius/titan-eye) public-data fetcher"
)
# Timeout más generoso por defecto: CelesTrak puede tardar varios segundos.
_DEFAULT_TIMEOUT = 45.0
# Reintentos con backoff ante fallos transitorios de red.
_DEFAULT_RETRIES = 3


@dataclass(frozen=True)
class TransportResponse:
    """Respuesta cruda de transporte: bytes exactos + contexto mínimo."""

    url: str
    status: int
    body: bytes
    media_type: str = "application/octet-stream"


class Transport(Protocol):
    """Contrato de transporte. Implementaciones: UrllibTransport, FakeTransport."""

    def get(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> TransportResponse: ...


class UrllibTransport:
    """Transporte real basado en `urllib` (stdlib). Sin dependencias externas.

    Envía un User-Agent honesto y reintenta los fallos transitorios de red con
    backoff: las APIs públicas (CelesTrak/OpenSky) responden mal a clientes
    anónimos y pueden fallar de forma intermitente."""

    def __init__(self, *, retries: int = _DEFAULT_RETRIES,
                 user_agent: str = _DEFAULT_USER_AGENT) -> None:
        self.retries = max(1, retries)
        self.user_agent = user_agent

    def get(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> TransportResponse:
        full = url
        if params:
            full = f"{url}?{urllib.parse.urlencode(params)}"
        hdrs = {"User-Agent": self.user_agent, "Accept": "*/*", **(headers or {})}
        req = urllib.request.Request(full, headers=hdrs, method="GET")
        last_exc: Exception | None = None
        for attempt in range(self.retries):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    body = resp.read()
                    media = resp.headers.get_content_type() or "application/octet-stream"
                    return TransportResponse(
                        url=full, status=resp.status, body=body, media_type=media)
            except urllib.error.HTTPError as exc:
                # Los 4xx no se reintentan (no son transitorios); 5xx sí.
                if exc.code < 500:
                    raise TransportError(f"HTTP {exc.code} desde {full}: {exc.reason}") from exc
                last_exc = exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_exc = exc
            if attempt < self.retries - 1:
                time.sleep(0.8 * (attempt + 1))  # backoff lineal suave
        reason = getattr(last_exc, "reason", last_exc)
        raise TransportError(
            f"Fallo de red contactando {full} tras {self.retries} intentos: {reason}"
        ) from last_exc


@dataclass
class FakeTransport:
    """Transporte de test. Devuelve respuestas pre-registradas por URL completa.

    Si se pide una URL no registrada, lanza ruidosamente: así cualquier intento
    de tocar red real en un test es inmediatamente visible.
    """

    responses: dict[str, TransportResponse] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)

    def register(self, full_url: str, body: bytes, *, status: int = 200,
                 media_type: str = "application/json") -> None:
        self.responses[full_url] = TransportResponse(
            url=full_url, status=status, body=body, media_type=media_type
        )

    def get(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> TransportResponse:
        full = url
        if params:
            full = f"{url}?{urllib.parse.urlencode(params)}"
        self.calls.append(full)
        if full not in self.responses:
            raise TransportError(
                f"FakeTransport: URL no registrada -> {full}. "
                f"Registradas: {sorted(self.responses)}"
            )
        return self.responses[full]
