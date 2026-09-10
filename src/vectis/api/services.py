"""Orquestração entre `vectis.data` e `vectis.quant` para a API web.

Isolado dos routers porque resolve duas preocupações que não são
"o que a rota HTTP retorna", e sim "como obter um dado confiável para
retornar": (1) o boletim de hoje pode ainda não estar publicado — é
preciso recuar pregão a pregão até achar liquidez; (2) o Focus não
cobre todo o horizonte de 10 anos — é preciso descobrir, na hora, até
onde dá para decompor o prêmio de risco. Nenhuma dessas é lógica de
apresentação HTTP, por isso fica aqui e não nos routers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from ..data import MarketDataRepository
from ..data.b3_di_client import B3RequestError
from ..data.calendar_br import latest_business_day
from ..data.models import DIVertex, FocusProjection, MarketIndicators
from ..quant import ETTJCurve, RiskPremiumResult, STANDARD_TENORS, risk_premium_best_effort
from .cache import TTLCache

_CURVE_CACHE_TTL_SECONDS = 300.0
_FOCUS_CACHE_TTL_SECONDS = 3600.0
_SNAPSHOT_CACHE_TTL_SECONDS = 300.0
_MAX_LOOKBACK_DAYS = 10


@dataclass(frozen=True, slots=True)
class CurveSnapshot:
    """O último pregão de DI1 com vértices líquidos disponíveis."""

    trade_date: date
    vertices: list[DIVertex]
    curve: ETTJCurve


_curve_cache: TTLCache[CurveSnapshot] = TTLCache(ttl_seconds=_CURVE_CACHE_TTL_SECONDS)
_focus_cache: TTLCache[FocusProjection | None] = TTLCache(ttl_seconds=_FOCUS_CACHE_TTL_SECONDS)
_snapshot_cache: TTLCache[MarketIndicators] = TTLCache(ttl_seconds=_SNAPSHOT_CACHE_TTL_SECONDS)


def get_latest_curve_snapshot(repo: MarketDataRepository) -> CurveSnapshot:
    """Curva do pregão mais recente com liquidez, recuando dia a dia se o
    boletim de hoje ainda não tiver sido publicado (a B3 fecha o ajuste
    só ao fim do pregão)."""

    def _load() -> CurveSnapshot:
        probe = date.today()
        for _ in range(_MAX_LOOKBACK_DAYS):
            resolved = latest_business_day(probe)
            try:
                vertices = repo.get_di_futures_curve(trade_date=resolved)
            except B3RequestError:
                # Falha transitória de rede num pregão específico não deve
                # derrubar o endpoint inteiro — tenta o pregão anterior.
                vertices = []
            if vertices:
                return CurveSnapshot(
                    trade_date=vertices[0].trade_date,
                    vertices=vertices,
                    curve=ETTJCurve.from_di_vertices(vertices),
                )
            probe = resolved - timedelta(days=1)
        raise ValueError(
            f"Nenhum pregão de DI1 líquido encontrado nos últimos {_MAX_LOOKBACK_DAYS} dias úteis."
        )

    return _curve_cache.get_or_set("latest", _load)


def get_focus_projection(repo: MarketDataRepository, year: int) -> FocusProjection | None:
    """Mediana Focus para `year`, ou None se o Focus não cobre esse ano."""

    def _load() -> FocusProjection | None:
        try:
            return repo.get_focus_selic_median(reference_year=year)
        except Exception:
            return None

    return _focus_cache.get_or_set(f"focus:{year}", _load)


def get_risk_premium(repo: MarketDataRepository, curve: ETTJCurve) -> RiskPremiumResult | None:
    """Prêmio de risco no vértice mais longo com cobertura Focus completa."""
    max_years = max(years for years, _months in STANDARD_TENORS.values())
    focus_by_year: dict[int, FocusProjection] = {}
    for year in range(curve.trade_date.year, curve.trade_date.year + max_years + 1):
        projection = get_focus_projection(repo, year)
        if projection is not None:
            focus_by_year[year] = projection

    return risk_premium_best_effort(curve, focus_by_year)


def get_market_snapshot_cached(repo: MarketDataRepository) -> MarketIndicators:
    return _snapshot_cache.get_or_set("snapshot", repo.get_market_snapshot)
