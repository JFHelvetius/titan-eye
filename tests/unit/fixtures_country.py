"""Fixture de fichas país SINTÉTICAS (ADR-0021). Países FICTICIOS, cifras inventadas."""

from __future__ import annotations

import json

COUNTRIES = [
    {"country": "Atlantia", "iso_code": "ATL", "region": "Norte",
     "military_budget_usd": 50_000_000_000, "budget_year": 2025,
     "active_personnel": 200_000, "reserve_personnel": 150_000,
     "alliances": ["NATO-like", "UN-like"], "source": "(SIPRI sintético)"},
    {"country": "Borealia", "iso_code": "BOR", "region": "Este",
     "military_budget_usd": 30_000_000_000, "budget_year": 2025,
     "active_personnel": 180_000, "alliances": ["CSTO-like", "UN-like"],
     "source": "(IISS sintético)"},
    # Ficha mínima (solo country): campos opcionales en None / lista vacía.
    {"country": "Meridia"},
]


def countries_payload() -> bytes:
    return json.dumps({"countries": COUNTRIES}).encode("utf-8")
