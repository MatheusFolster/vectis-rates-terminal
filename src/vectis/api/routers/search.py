"""GET /api/search — barra de comando: código de contrato DI1, série SGS
ou data. Uma consulta pode responder a mais de um tipo (ex.: "432"
casa com o código da série Selic meta); por isso cada detector devolve
uma lista, e a resposta é a concatenação de todos os que casaram."""

from __future__ import annotations

import re
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query

from .. import services
from ..dependencies import get_repository
from ..schemas import SearchResponse, SearchResult
from ...data import MarketDataRepository
from ...data.b3_di_client import B3RequestError
from ...data.b3_di_parsers import InvalidDIContractCode, di_maturity_date
from ...data.series_codes import IPCA_MENSAL, SELIC_EFETIVA_ANUALIZADA, SELIC_META
from ...data.models import TimeSeries

router = APIRouter(prefix="/api", tags=["search"])

_DI_CODE_RE = re.compile(r"^DI1[FGHJKMNQUVXZ]\d{2}$")
_DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y")


@router.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1, description="Código DI1, série SGS ou data (dd/mm/aaaa)."),
    repo: MarketDataRepository = Depends(get_repository),
) -> SearchResponse:
    query = q.strip()
    results: list[SearchResult] = []

    results.extend(_search_di_contract(query, repo))
    results.extend(_search_sgs_series(query, repo))
    results.extend(_search_date(query, repo))

    return SearchResponse(query=query, results=results)


def _search_di_contract(query: str, repo: MarketDataRepository) -> list[SearchResult]:
    code = query.upper().replace(" ", "")
    if not _DI_CODE_RE.match(code):
        return []
    try:
        maturity = di_maturity_date(code)
    except InvalidDIContractCode:
        return []

    try:
        snapshot = services.get_latest_curve_snapshot(repo)
    except ValueError:
        return [
            SearchResult(
                type="di_contract",
                label=code,
                value=None,
                unit="% a.a.",
                reference_date=maturity,
                detail=f"Vencimento {maturity:%d/%m/%Y} — sem pregão de DI1 líquido disponível no momento.",
            )
        ]

    for v in snapshot.vertices:
        if v.code == code:
            return [
                SearchResult(
                    type="di_contract",
                    label=v.code,
                    value=v.settlement_rate,
                    unit="% a.a.",
                    reference_date=v.maturity,
                    detail=(
                        f"Vencimento {v.maturity:%d/%m/%Y} · {v.business_days_to_maturity} du · "
                        f"PU {v.settlement_pu:,.2f} · pregão {snapshot.trade_date:%d/%m/%Y}"
                    ),
                )
            ]

    return [
        SearchResult(
            type="di_contract",
            label=code,
            value=None,
            unit="% a.a.",
            reference_date=maturity,
            detail=f"Vencimento {maturity:%d/%m/%Y} — sem liquidez suficiente no pregão de {snapshot.trade_date:%d/%m/%Y}.",
        )
    ]


def _sgs_series_registry(repo: MarketDataRepository):
    return (
        (SELIC_META, repo.get_selic_meta_series),
        (SELIC_EFETIVA_ANUALIZADA, repo.get_selic_efetiva_series),
        (IPCA_MENSAL, repo.get_ipca_series),
    )


def _search_sgs_series(query: str, repo: MarketDataRepository) -> list[SearchResult]:
    normalized = re.sub(r"(?i)\bsgs\b", "", query).strip().lower()
    if not normalized:
        return []

    results: list[SearchResult] = []
    for series_def, get_series in _sgs_series_registry(repo):
        matches_code = normalized == str(series_def.code)
        matches_name = normalized in series_def.name.lower()
        if not (matches_code or matches_name):
            continue

        series: TimeSeries = get_series(last_n=1)
        point = series.latest()
        if point is None:
            continue

        unit = "%" if "ipca" in series_def.name.lower() else "% a.a."
        results.append(
            SearchResult(
                type="sgs_series",
                label=f"SGS {series_def.code} — {series_def.name}",
                value=point.value,
                unit=unit,
                reference_date=point.date,
                detail=f"Última leitura em {point.date:%d/%m/%Y}.",
            )
        )
    return results


def _parse_date(value: str) -> date | None:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _search_date(query: str, repo: MarketDataRepository) -> list[SearchResult]:
    parsed = _parse_date(query.strip())
    if parsed is None:
        return []

    try:
        vertices = repo.get_di_futures_curve(trade_date=parsed)
    except B3RequestError:
        return [
            SearchResult(
                type="date",
                label=f"{parsed:%d/%m/%Y}",
                value=None,
                unit=None,
                reference_date=parsed,
                detail="Falha temporária ao consultar o boletim da B3 para esta data — tente novamente.",
            )
        ]
    if not vertices:
        return [
            SearchResult(
                type="date",
                label=f"{parsed:%d/%m/%Y}",
                value=None,
                unit=None,
                reference_date=parsed,
                detail="Sem vértices líquidos de DI1 nesta data (sem pregão, ou boletim ainda não publicado).",
            )
        ]

    resolved = vertices[0].trade_date
    note = "" if resolved == parsed else f" (pregão mais próximo: {resolved:%d/%m/%Y})"
    return [
        SearchResult(
            type="date",
            label=f"{parsed:%d/%m/%Y}",
            value=float(len(vertices)),
            unit="vértices",
            reference_date=resolved,
            detail=(
                f"Pregão com {len(vertices)} vértices líquidos de DI1 "
                f"({vertices[0].business_days_to_maturity} a {vertices[-1].business_days_to_maturity} du).{note}"
            ),
        )
    ]
