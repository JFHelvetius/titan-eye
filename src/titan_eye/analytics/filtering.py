"""Filtro de vista transversal por país y tipo (ADR-0018).

Funciones PURAS que seleccionan entradas del payload del globo por su `country`
y/o su `kind` (clase filtrable declarada por cada traductor). No añaden inferencia
ni recalculan agregados: solo seleccionan lo ya observado. Una entrada con
`country`/`kind` vacío se descarta cuando ese eje tiene una selección activa
(vacío = "el dato no lo soporta", no coincide con ningún país/tipo concreto).
"""

from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy

_DOMAINS = ("orbital", "aerial", "maritime", "suborbital", "surface")


def _keep(entry: dict, countries: set[str] | None, kinds: set[str] | None) -> bool:
    if countries is not None and entry.get("country", "") not in countries:
        return False
    return not (kinds is not None and entry.get("kind", "") not in kinds)


def filter_payload(
    payload: dict,
    *,
    countries: Iterable[str] | None = None,
    kinds: Iterable[str] | None = None,
) -> dict:
    """Devuelve una copia del payload con solo las entradas que casan país y tipo.

    Sin selección en un eje (None o vacío), ese eje no filtra. El mapa de calor NO
    se recalcula (es un agregado aparte, ADR-0018); se conserva tal cual."""
    cset = {c for c in countries if c} if countries else None
    kset = {k for k in kinds if k} if kinds else None
    if cset is None and kset is None:
        return payload  # sin filtro: sin copia

    out = deepcopy(payload)
    domains = out.get("domains", {})
    for dom in _DOMAINS:
        domains[dom] = [e for e in domains.get(dom, []) if _keep(e, cset, kset)]
    if "installations" in out:
        out["installations"] = [e for e in out["installations"] if _keep(e, cset, kset)]
    return out


def available_countries(payload: dict) -> list[str]:
    """Países presentes (no vacíos) en el payload, ordenados — para los selectores."""
    return sorted(_collect(payload, "country"))


def available_kinds(payload: dict) -> list[str]:
    """Tipos/clases presentes (no vacíos) en el payload, ordenados."""
    return sorted(_collect(payload, "kind"))


def _collect(payload: dict, key: str) -> set[str]:
    vals: set[str] = set()
    domains = payload.get("domains", {})
    for dom in _DOMAINS:
        for e in domains.get(dom, []):
            v = e.get(key, "")
            if v:
                vals.add(v)
    for e in payload.get("installations", []):
        v = e.get(key, "")
        if v:
            vals.add(v)
    return vals
