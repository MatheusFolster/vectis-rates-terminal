"""Calendário de dias úteis nacional (feriados ANBIMA/B3).

Isolado em módulo próprio porque é usado tanto para decodificar o
vencimento de contratos DI1 (b3_di_parsers.py) quanto, mais adiante,
pelo motor quant para contar prazos em dias úteis (convenção 252).
"""

from __future__ import annotations

from datetime import date, timedelta

from dateutil.easter import easter


def _fixed_holidays(year: int) -> set[date]:
    return {
        date(year, 1, 1),  # Confraternização Universal
        date(year, 4, 21),  # Tiradentes
        date(year, 5, 1),  # Dia do Trabalho
        date(year, 9, 7),  # Independência do Brasil
        date(year, 10, 12),  # Nossa Senhora Aparecida
        date(year, 11, 2),  # Finados
        date(year, 11, 15),  # Proclamação da República
        date(year, 12, 25),  # Natal
    }


def _moveable_holidays(year: int) -> set[date]:
    e = easter(year)
    return {
        e - timedelta(days=48),  # Segunda-feira de Carnaval
        e - timedelta(days=47),  # Terça-feira de Carnaval
        e - timedelta(days=2),  # Sexta-feira Santa
        e + timedelta(days=60),  # Corpus Christi
    }


def holidays(year: int) -> set[date]:
    """Feriados nacionais observados pela B3 (calendário ANBIMA)."""
    return _fixed_holidays(year) | _moveable_holidays(year)


def is_business_day(d: date) -> bool:
    return d.weekday() < 5 and d not in holidays(d.year)


def business_days_between(start: date, end: date) -> int:
    """Dias úteis estritamente após `start` até `end`, inclusive.

    Segue a convenção de mercado (base 252): o dia de referência (`start`)
    não conta, o dia de vencimento (`end`) conta.
    """
    if end <= start:
        return 0
    count = 0
    current = start + timedelta(days=1)
    while current <= end:
        if is_business_day(current):
            count += 1
        current += timedelta(days=1)
    return count


def latest_business_day(d: date) -> date:
    """`d` se for dia útil, caso contrário o dia útil imediatamente anterior."""
    current = d
    while not is_business_day(current):
        current -= timedelta(days=1)
    return current


def add_business_days(start: date, n: int) -> date:
    """O n-ésimo dia útil após `start` (inverso de `business_days_between`).

    Usada pela camada de API para desenhar a grade de datas da curva
    interpolada a partir de um prazo em dias úteis, sem recalcular a
    curva inteira em termos de datas.
    """
    if n <= 0:
        return start
    current = start
    count = 0
    while count < n:
        current += timedelta(days=1)
        if is_business_day(current):
            count += 1
    return current
