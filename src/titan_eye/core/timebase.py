"""Reloj inyectable y utilidades de tiempo UTC.

Todo el sistema opera en UTC declarado (precondición de P1, reproducibilidad
bajo entorno declarado). El reloj se inyecta para que los tests sean
deterministas y no dependan del reloj de la máquina (ADR-0013 planificado).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """Fuente de tiempo. `now()` devuelve siempre un datetime aware en UTC."""

    def now(self) -> datetime: ...


class SystemClock:
    """Reloj real del sistema, normalizado a UTC."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    """Reloj fijo para tests; devuelve siempre el mismo instante UTC."""

    def __init__(self, fixed: datetime) -> None:
        if fixed.tzinfo is None:
            raise ValueError("FixedClock requiere un datetime aware (con tzinfo).")
        self._fixed = fixed.astimezone(UTC)

    def now(self) -> datetime:
        return self._fixed


def from_unix(seconds: float) -> datetime:
    """Convierte un timestamp Unix (segundos) a datetime aware UTC.

    OpenSky y muchas fuentes públicas reportan tiempos como epoch Unix."""
    return datetime.fromtimestamp(seconds, tz=UTC)


def to_iso(dt: datetime) -> str:
    """ISO-8601 en UTC con sufijo Z, determinista para serialización canónica."""
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")
