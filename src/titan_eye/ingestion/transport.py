"""Transporte HTTP inyectable.

El `Transport` es un Protocol para que las fuentes se testeen sin red: en tests
se inyecta un `FakeTransport` con respuestas pre-registradas (cualquier escape a
red se vuelve visible inmediatamente). En producción, `UrllibTransport` usa solo
stdlib — cero dependencias nuevas (P3).
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol

from titan_eye.core.errors import TransportError


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
    """Transporte real basado en `urllib` (stdlib). Sin dependencias externas."""

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
        req = urllib.request.Request(full, headers=headers or {}, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                media = resp.headers.get_content_type() or "application/octet-stream"
                return TransportResponse(url=full, status=resp.status, body=body, media_type=media)
        except urllib.error.HTTPError as exc:
            raise TransportError(f"HTTP {exc.code} desde {full}: {exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise TransportError(f"Fallo de red contactando {full}: {exc.reason}") from exc
        except TimeoutError as exc:
            raise TransportError(f"Timeout contactando {full}") from exc


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
