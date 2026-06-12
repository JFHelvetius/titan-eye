"""Normalizador puro: RawArtifact de CelesTrak (texto TLE) -> list[OrbitalElement].

Determinista, sin red. Parser TLE por columnas (formato fijo NORAD/Spacetrack),
tolerante a bloques de 2 líneas (sin nombre) y 3 líneas (con nombre), CRLF y
líneas en blanco. Conserva las dos líneas originales y computa el
`tle_content_hash = sha256(line1+"\\n"+line2)` para la cadena de procedencia.

Honestidad (P2): si una línea no cumple el formato esperado, se lanza
`NormalizationError` con línea/columna; no se adivinan valores.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

from titan_eye.catalog.orbital import OrbitalElement
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.errors import NormalizationError
from titan_eye.ingestion.artifact import RawArtifact

TLE_NORMALIZER_VERSION = "0.1.0"


def normalize_tles(artifact: RawArtifact) -> list[OrbitalElement]:
    """Convierte el texto TLE del artefacto en una lista de OrbitalElement."""
    try:
        text = artifact.payload.decode("ascii")
    except UnicodeDecodeError as exc:
        raise NormalizationError(
            "Payload TLE no es ASCII válido", source_hash=artifact.content_hash
        ) from exc

    out: list[OrbitalElement] = []
    for name, line1, line2, line_no in _iter_tle_blocks(text):
        out.append(_parse_block(name, line1, line2, line_no, artifact))
    return out


def _iter_tle_blocks(text: str) -> Iterator[tuple[str | None, str, str, int]]:
    """Itera bloques TLE. Soporta 2-line y 3-line, CRLF y blancos."""
    raw_lines = [ln.rstrip("\r") for ln in text.split("\n")]
    lines = [(i, ln) for i, ln in enumerate(raw_lines) if ln.strip()]
    i = 0
    while i < len(lines):
        idx, ln = lines[i]
        if ln.startswith("1 ") and i + 1 < len(lines) and lines[i + 1][1].startswith("2 "):
            yield None, ln, lines[i + 1][1], idx
            i += 2
        elif (
            not ln.startswith(("1 ", "2 "))
            and i + 2 < len(lines)
            and lines[i + 1][1].startswith("1 ")
            and lines[i + 2][1].startswith("2 ")
        ):
            yield ln.strip(), lines[i + 1][1], lines[i + 2][1], idx
            i += 3
        else:
            raise NormalizationError(
                f"Bloque TLE no reconocido cerca de la línea {idx}: {ln[:30]!r}",
                line=idx,
            )


def _parse_block(
    name: str | None, line1: str, line2: str, line_no: int, artifact: RawArtifact
) -> OrbitalElement:
    if len(line1) < 64 or len(line2) < 63:
        raise NormalizationError(
            f"Líneas TLE demasiado cortas en bloque {line_no} "
            f"(l1={len(line1)}, l2={len(line2)})",
            source_hash=artifact.content_hash, line=line_no,
        )
    try:
        norad = int(line1[2:7])
        intl = line1[9:17].strip() or None
        epoch = _parse_epoch(line1[18:32])
        incl = float(line2[8:16])
        raan = float(line2[17:25])
        ecc = float("0." + line2[26:33].strip())
        argp = float(line2[34:42])
        ma = float(line2[43:51])
        mm = float(line2[52:63])
    except (ValueError, IndexError) as exc:
        raise NormalizationError(
            f"Campo TLE inválido en bloque {line_no}: {exc}",
            source_hash=artifact.content_hash, line=line_no,
        ) from exc

    tle_hash = hashlib.sha256((line1 + "\n" + line2).encode("ascii")).hexdigest()
    return OrbitalElement(
        norad_cat_id=norad,
        object_name=name,
        intl_designator=intl,
        line1=line1,
        line2=line2,
        epoch=epoch,
        inclination_deg=incl,
        raan_deg=raan,
        eccentricity=ecc,
        arg_perigee_deg=argp,
        mean_anomaly_deg=ma,
        mean_motion_rev_per_day=mm,
        content_hash_source=artifact.content_hash,
        tle_content_hash=tle_hash,
        epistemic_label=EpistemicLabel.OBSERVED,
    )


def _parse_epoch(field: str) -> datetime:
    """Época TLE 'YYDDD.DDDDDDDD' -> datetime UTC. YY<57 => 20YY, si no 19YY."""
    field = field.strip()
    yy = int(field[:2])
    year = 2000 + yy if yy < 57 else 1900 + yy
    day_of_year = float(field[2:])
    # día 1.0 = 1 enero 00:00 UTC
    return datetime(year, 1, 1, tzinfo=UTC) + timedelta(days=day_of_year - 1.0)
