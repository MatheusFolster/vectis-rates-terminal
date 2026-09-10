"""Registro central dos códigos de série usados pelo terminal.

Manter os códigos num único lugar evita "números mágicos" espalhados
pelos clientes e facilita adicionar novas séries (ex.: câmbio, IGP-M)
sem tocar na lógica de requisição.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SGSSeriesDef:
    code: int
    name: str
    source: str = "BCB/SGS"


# Códigos oficiais do Sistema Gerenciador de Séries Temporais (SGS/BCB).
SELIC_META = SGSSeriesDef(code=432, name="Selic meta definida pelo Copom")
SELIC_EFETIVA_ANUALIZADA = SGSSeriesDef(
    code=4189, name="Selic efetiva acumulada no mês, anualizada (base 252)"
)
IPCA_MENSAL = SGSSeriesDef(code=433, name="IPCA - variação mensal")

# Indicador do Focus (Expectativas de Mercado - Olinda/BCB).
FOCUS_INDICATOR_SELIC = "Selic"
