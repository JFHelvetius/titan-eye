"""Normalizador puro: RawArtifact (GDELT DOC JSON) -> list[OsintItem] (ADR-0020).

Determinista, sin red. GDELT DOC devuelve artículos con `sourcecountry` (país del
medio) pero SIN coordenadas del suceso. Honestidad (P2/P9): geolocalizamos cada
artículo en el **centroide del país de la FUENTE**, no en el lugar del hecho, y lo
declaramos explícitamente en el resumen. Es una afirmación de terceros (`asserted`):
Titan Eye no verifica veracidad (ADR-0020).

Para que muchos artículos del mismo país no se apilen en un punto, se aplica un
desplazamiento determinista en espiral (solo para legibilidad, NO es precisión).
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from typing import Any

from titan_eye.catalog.osint import OsintItem, SourceTier
from titan_eye.core.epistemics import EpistemicLabel
from titan_eye.core.errors import NormalizationError
from titan_eye.ingestion.artifact import RawArtifact

GDELT_DOC_NORMALIZER_VERSION = "0.1.0"

# Centroides aproximados (lat, lon) por país de fuente de GDELT (nombres en inglés
# tal y como los emite la API). Cobertura amplia con foco en países de relevancia
# militar; los artículos de países no mapeados se omiten (no se inventa ubicación).
_CENTROIDS: dict[str, tuple[float, float]] = {
    "United States": (39.8, -98.6), "Russia": (61.5, 105.3), "China": (35.9, 104.2),
    "Ukraine": (48.4, 31.2), "United Kingdom": (54.0, -2.0), "France": (46.6, 2.4),
    "Germany": (51.2, 10.4), "Israel": (31.0, 34.8), "Iran": (32.4, 53.7),
    "India": (22.0, 79.0), "Pakistan": (30.4, 69.3), "Japan": (36.2, 138.3),
    "South Korea": (36.5, 127.8), "North Korea": (40.3, 127.5), "Turkey": (39.0, 35.2),
    "Syria": (35.0, 38.5), "Iraq": (33.2, 43.7), "Saudi Arabia": (24.0, 45.1),
    "Yemen": (15.6, 48.0), "Egypt": (26.8, 30.8), "Lebanon": (33.9, 35.9),
    "Jordan": (31.3, 36.5), "Afghanistan": (33.9, 67.7), "Poland": (51.9, 19.1),
    "Italy": (42.8, 12.6), "Spain": (40.0, -3.7), "Taiwan": (23.7, 121.0),
    "Australia": (-25.3, 133.8), "Canada": (56.1, -106.3), "Brazil": (-14.2, -51.9),
    "Mexico": (23.6, -102.5), "Sweden": (62.2, 17.6), "Finland": (64.9, 26.1),
    "Norway": (64.6, 17.9), "Netherlands": (52.1, 5.3), "Belgium": (50.6, 4.6),
    "Greece": (39.1, 21.8), "Romania": (45.9, 24.9), "Czech Republic": (49.8, 15.5),
    "Hungary": (47.2, 19.5), "Austria": (47.6, 14.1), "Switzerland": (46.8, 8.2),
    "Portugal": (39.6, -8.0), "Denmark": (56.1, 9.5), "Ireland": (53.2, -8.0),
    "Estonia": (58.6, 25.0), "Latvia": (56.9, 24.6), "Lithuania": (55.2, 23.9),
    "Belarus": (53.7, 27.9), "Georgia": (42.3, 43.4), "Armenia": (40.1, 45.0),
    "Azerbaijan": (40.1, 47.6), "Kazakhstan": (48.0, 66.9), "Libya": (26.3, 17.2),
    "Sudan": (12.9, 30.2), "Ethiopia": (9.1, 40.5), "Somalia": (5.2, 46.2),
    "Nigeria": (9.1, 8.7), "Mali": (17.6, -4.0), "Algeria": (28.0, 1.7),
    "Morocco": (31.8, -7.1), "Tunisia": (33.9, 9.5), "South Africa": (-30.6, 22.9),
    "Venezuela": (6.4, -66.6), "Colombia": (4.6, -74.3), "Argentina": (-38.4, -63.6),
    "Indonesia": (-0.8, 113.9), "Philippines": (12.9, 121.8), "Vietnam": (14.1, 108.3),
    "Thailand": (15.9, 100.99), "Myanmar": (21.9, 95.96), "Malaysia": (4.2, 101.98),
    "Singapore": (1.35, 103.8), "Bangladesh": (23.7, 90.4), "Sri Lanka": (7.9, 80.8),
    "New Zealand": (-41.0, 174.0), "Qatar": (25.3, 51.2), "United Arab Emirates": (23.4, 53.8),
    "Kuwait": (29.3, 47.5), "Bahrain": (26.0, 50.5), "Oman": (21.5, 55.9),
    "Cuba": (21.5, -77.8), "Serbia": (44.0, 21.0), "Croatia": (45.1, 15.2),
    "Bulgaria": (42.7, 25.5), "Slovakia": (48.7, 19.7), "Moldova": (47.4, 28.4),
}

# Mapeo (parcial) de país de fuente a un país ISO-ish para el campo `country`.
_TIER = SourceTier.NEWS_AGENCY


def normalize_gdelt_doc(artifact: RawArtifact) -> list[OsintItem]:
    """Convierte el JSON de artículos GDELT en OsintItem geolocalizados (asserted)."""
    try:
        doc: Any = json.loads(artifact.payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NormalizationError(
            "Respuesta GDELT no es JSON UTF-8 válido", source_hash=artifact.content_hash
        ) from exc

    articles = doc.get("articles") if isinstance(doc, dict) else doc
    if not isinstance(articles, list):
        raise NormalizationError(
            "Respuesta GDELT sin lista 'articles'", source_hash=artifact.content_hash
        )

    out: list[OsintItem] = []
    per_country: dict[str, int] = {}
    for art in articles:
        if not isinstance(art, dict):
            continue
        country = str(art.get("sourcecountry") or "").strip()
        coord = _CENTROIDS.get(country)
        if coord is None:
            continue  # sin centroide conocido -> no se dibuja (P2: no se inventa)
        k = per_country.get(country, 0)
        per_country[country] = k + 1
        lat, lon = _spread(coord, k)
        out.append(_to_item(art, country, lat, lon, artifact))
    return out


def _to_item(
    art: dict, country: str, lat: float, lon: float, artifact: RawArtifact
) -> OsintItem:
    url = str(art.get("url") or "")
    title = str(art.get("title") or "(sin título)")
    item_id = "gdelt-" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return OsintItem(
        item_id=item_id,
        title=title[:300],
        latitude=lat,
        longitude=lon,
        source=str(art.get("domain") or "GDELT"),
        source_url=url,
        source_tier=_TIER,
        published_at=_parse_seendate(art.get("seendate")),
        country=country,
        summary=("Geolocalizado por PAÍS DE LA FUENTE (no el lugar del suceso). "
                 f"Idioma: {art.get('language', '—')}. Afirmación de prensa · GDELT · "
                 "no verificado por Titan Eye."),
        content_hash_source=artifact.content_hash,
        epistemic_label=EpistemicLabel.ASSERTED,
    )


def _parse_seendate(raw: Any) -> datetime | None:
    """GDELT 'YYYYMMDDTHHMMSSZ' -> datetime UTC."""
    if not raw:
        return None
    s = str(raw).strip()
    try:
        return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def _spread(coord: tuple[float, float], k: int) -> tuple[float, float]:
    """Desplazamiento determinista en espiral (solo legibilidad, no precisión)."""
    if k == 0:
        return coord
    ang = k * 2.399963  # ángulo áureo -> reparto uniforme
    rad = 0.45 * math.sqrt(k)  # grados; crece despacio
    lat = max(-85.0, min(85.0, coord[0] + rad * math.sin(ang)))
    lon = coord[1] + rad * math.cos(ang)
    if lon > 180:
        lon -= 360
    elif lon < -180:
        lon += 360
    return (round(lat, 4), round(lon, 4))
