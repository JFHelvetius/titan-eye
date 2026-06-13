"""Fixture de ítems OSINT SINTÉTICOS (ADR-0020). No son noticias reales.

Mezcla de tiers de fuente, uno sin tier (-> other) y uno con published_at."""

from __future__ import annotations

import json

OSINT_ITEMS = [
    {"item_id": "N1", "title": "Reporte de agencia demo", "latitude": 47.9, "longitude": 37.5,
     "source": "Agencia Sintética", "source_url": "https://example.org/n1",
     "source_tier": "news_agency", "published_at": "2026-06-10T08:00:00Z", "country": "Borealia"},
    {"item_id": "N2", "title": "Comunicado oficial demo", "latitude": 48.0, "longitude": 37.6,
     "source": "Gobierno Sintético", "source_tier": "government", "country": "Borealia"},
    {"item_id": "N3", "title": "Publicación RRSS demo", "latitude": 48.3, "longitude": 36.9,
     "source": "@usuario_sintetico", "source_tier": "social_media", "country": "Borealia"},
    # Sin tier -> other.
    {"item_id": "N4", "title": "Item sin tier", "latitude": 49.0, "longitude": 30.0,
     "source": "?", "country": "Atlantia"},
]


def osint_payload() -> bytes:
    return json.dumps({"items": OSINT_ITEMS}).encode("utf-8")
