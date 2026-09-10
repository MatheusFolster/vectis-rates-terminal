"""Decodificação de códigos de contrato futuro de DI1 (B3).

Puro e sem I/O — só depende do calendário de dias úteis — para poder ser
testado isoladamente do cliente HTTP.
"""

from __future__ import annotations

from datetime import date, timedelta

from .calendar_br import is_business_day

_MONTH_CODE = {
    "F": 1,
    "G": 2,
    "H": 3,
    "J": 4,
    "K": 5,
    "M": 6,
    "N": 7,
    "Q": 8,
    "U": 9,
    "V": 10,
    "X": 11,
    "Z": 12,
}


class InvalidDIContractCode(ValueError):
    """Código de contrato fora do padrão DI1<letra do mês><AA>, ex.: DI1F29."""


def parse_di_contract_code(code: str) -> tuple[int, int]:
    """Extrai (mês, ano) de um código de contrato DI1. Ex.: 'DI1F29' -> (1, 2029)."""
    if not code.startswith("DI1") or len(code) != 6:
        raise InvalidDIContractCode(code)

    letter, digits = code[3], code[4:]
    month = _MONTH_CODE.get(letter)
    if month is None or not digits.isdigit():
        raise InvalidDIContractCode(code)

    return month, 2000 + int(digits)


def di_maturity_date(code: str) -> date:
    """Vencimento do contrato: primeiro dia útil do mês/ano do contrato."""
    month, year = parse_di_contract_code(code)
    candidate = date(year, month, 1)
    while not is_business_day(candidate):
        candidate += timedelta(days=1)
    return candidate
