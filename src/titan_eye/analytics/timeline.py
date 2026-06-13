"""Línea temporal histórica — replay sobre el store append-only (ADR-0019).

Funciones PURAS sobre una lista de `TimelineItem` (cada uno: fecha ISO, dominio,
y la entrada de globo ya traducida). No inventan datos entre días ni rellenan
huecos: un día sin datos es un día vacío (P2). La serie y el replay son Derived
on-demand sobre lo ya persistido (ADR-0006).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Dominios que participan de la línea temporal v0.1 (ADR-0019).
TIMELINE_DOMAINS = ("aerial", "maritime", "surface")


@dataclass(frozen=True)
class TimelineItem:
    """Una detección persistida situada en el tiempo para el replay."""

    date: str          # ISO 'YYYY-MM-DD' (event_date en superficie; día de snapshot en aéreo/mar)
    domain: str
    entry: dict        # entrada de globo (ya traducida)


@dataclass(frozen=True)
class DayActivity:
    """Conteo por dominio en un día (un punto de la serie temporal)."""

    date: str
    counts: dict[str, int]
    total: int


def date_range(items: list[TimelineItem]) -> tuple[str, str] | None:
    """(primer día, último día) presentes, o None si no hay datos."""
    dates = sorted({it.date for it in items})
    return (dates[0], dates[-1]) if dates else None


def available_days(items: list[TimelineItem]) -> list[str]:
    """Días con datos, ordenados ascendentemente."""
    return sorted({it.date for it in items})


def daily_activity(items: list[TimelineItem]) -> list[DayActivity]:
    """Serie temporal: conteo por dominio por día (evolución día a día)."""
    by_day: dict[str, dict[str, int]] = {}
    for it in items:
        counts = by_day.setdefault(it.date, {})
        counts[it.domain] = counts.get(it.domain, 0) + 1
    out: list[DayActivity] = []
    for day in sorted(by_day):
        counts = by_day[day]
        out.append(DayActivity(date=day, counts=dict(counts), total=sum(counts.values())))
    return out


def payload_for_day(items: list[TimelineItem], day: str) -> dict:
    """Reconstruye el payload del globo con SOLO las entradas de `day` (replay)."""
    domains: dict[str, list] = {"orbital": [], "aerial": [], "maritime": [],
                                "suborbital": [], "surface": []}
    for it in items:
        if it.date == day and it.domain in domains:
            domains[it.domain].append(it.entry)
    return {
        "domains": domains,
        "heatmap": [],
        "installations": [],
        "layers": {d: True for d in domains} | {"heatmap": False, "range": False,
                                                "installations": False},
        "replay_day": day,
    }


@dataclass(frozen=True)
class TimelineSummary:
    """Resumen serializable de la serie temporal (para CLI/API)."""

    n_items: int
    first_day: str | None
    last_day: str | None
    days: list[DayActivity] = field(default_factory=list)


def summarize(items: list[TimelineItem]) -> TimelineSummary:
    rng = date_range(items)
    return TimelineSummary(
        n_items=len(items),
        first_day=rng[0] if rng else None,
        last_day=rng[1] if rng else None,
        days=daily_activity(items),
    )
