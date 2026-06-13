"""Tests de la línea temporal histórica (ADR-0019): replay puro, sin inventar huecos."""

from __future__ import annotations

from titan_eye.analytics.timeline import (
    TimelineItem,
    available_days,
    daily_activity,
    date_range,
    payload_for_day,
    summarize,
)


def _items() -> list[TimelineItem]:
    return [
        TimelineItem("2026-06-08", "surface", {"id": "E1"}),
        TimelineItem("2026-06-08", "surface", {"id": "E2"}),
        TimelineItem("2026-06-08", "maritime", {"id": "V1"}),
        TimelineItem("2026-06-10", "surface", {"id": "E3"}),
        TimelineItem("2026-06-10", "aerial", {"id": "A1"}),
    ]


def test_empty() -> None:
    assert date_range([]) is None
    assert available_days([]) == []
    assert daily_activity([]) == []


def test_date_range_and_days() -> None:
    items = _items()
    assert date_range(items) == ("2026-06-08", "2026-06-10")
    # 06-09 NO aparece: día sin datos = vacío, no se inventa (ADR-0019)
    assert available_days(items) == ["2026-06-08", "2026-06-10"]


def test_daily_activity_counts() -> None:
    days = {d.date: d for d in daily_activity(_items())}
    assert days["2026-06-08"].counts == {"surface": 2, "maritime": 1}
    assert days["2026-06-08"].total == 3
    assert days["2026-06-10"].counts == {"surface": 1, "aerial": 1}


def test_payload_for_day_replay() -> None:
    p = payload_for_day(_items(), "2026-06-08")
    assert {e["id"] for e in p["domains"]["surface"]} == {"E1", "E2"}
    assert {e["id"] for e in p["domains"]["maritime"]} == {"V1"}
    assert p["domains"]["aerial"] == []          # ese día no hubo aéreo
    assert p["replay_day"] == "2026-06-08"


def test_payload_for_empty_day() -> None:
    # Un día sin datos devuelve payload vacío (no se interpola).
    p = payload_for_day(_items(), "2026-06-09")
    assert all(v == [] for v in p["domains"].values())


def test_summarize() -> None:
    s = summarize(_items())
    assert s.n_items == 5
    assert s.first_day == "2026-06-08" and s.last_day == "2026-06-10"
    assert len(s.days) == 2
