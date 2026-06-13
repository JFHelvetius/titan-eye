"""Tests del enum de dominios (ADR-0000, ADR-0001)."""

from __future__ import annotations

from titan_eye.core.domains import DOMAIN_UNCERTAINTY_NOTE, Domain


def test_domains_exist() -> None:
    assert {d.value for d in Domain} == {
        "orbital", "suborbital", "aerial", "surface", "maritime", "reference", "osint"
    }


def test_every_domain_declares_uncertainty() -> None:
    # P2: ningún dominio puede existir sin nota de incertidumbre declarada.
    for d in Domain:
        assert d in DOMAIN_UNCERTAINTY_NOTE
        assert DOMAIN_UNCERTAINTY_NOTE[d].strip()


def test_domain_is_str_enum() -> None:
    assert Domain.AERIAL == "aerial"
