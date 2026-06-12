"""Fixture canónica TLE: ISS (ZARYA), Vallado 2008. Estándar de validación SGP4."""

from __future__ import annotations

ISS_NAME = "ISS (ZARYA)"
ISS_LINE1 = "1 25544U 98067A   08264.51782528 -.00002182  00000-0 -11606-4 0  2927"
ISS_LINE2 = "2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.72125391563537"

# Bloque de 3 líneas (con nombre) + un segundo satélite sintético de 2 líneas.
TLE_TEXT_3LINE = f"{ISS_NAME}\n{ISS_LINE1}\n{ISS_LINE2}\n"

TLE_TEXT_MULTI = (
    f"{ISS_NAME}\n{ISS_LINE1}\n{ISS_LINE2}\n"
    "CSS (TIANHE)\n"
    "1 48274U 21035A   24001.50000000  .00010000  00000-0  10000-3 0  9999\n"
    "2 48274  41.4700 100.0000 0005000  90.0000 270.0000 15.60000000123456\n"
)


def iss_payload() -> bytes:
    return TLE_TEXT_3LINE.encode("ascii")


def multi_payload() -> bytes:
    return TLE_TEXT_MULTI.encode("ascii")
