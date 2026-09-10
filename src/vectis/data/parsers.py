"""Utilitários de parsing isolados dos clientes HTTP.

Centralizar aqui evita duplicar conversão de data/número em cada cliente
de API (SGS, Focus, e futuramente B3).
"""

from __future__ import annotations

from datetime import date, datetime


def parse_br_date(value: str) -> date:
    """Converte data no formato dd/mm/aaaa (padrão do SGS/BCB)."""
    return datetime.strptime(value, "%d/%m/%Y").date()


def parse_iso_date(value: str) -> date:
    """Converte data no formato aaaa-mm-dd (padrão da API Olinda/Focus)."""
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def parse_number(value: str | float | int) -> float:
    """Converte valores numéricos vindos da API do BCB para float."""
    if isinstance(value, (float, int)):
        return float(value)
    return float(str(value).replace(",", "."))
