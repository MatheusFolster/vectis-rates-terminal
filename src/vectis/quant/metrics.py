"""Métricas analíticas extraídas de uma `ETTJCurve`.

Mantido separado de `curve.py` porque aqui vivem decisões de "o que
mostrar" (vértices padronizados, pares de forward, decomposição contra
o Focus) — não de "como a curva é construída". `curve.py` não sabe o
que é "1A" ou "Focus"; este módulo traduz essas convenções de mercado
em chamadas à API pura da curva.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from ..data.calendar_br import business_days_between, is_business_day
from ..data.models import FocusProjection
from .curve import BUSINESS_DAYS_PER_YEAR, ETTJCurve

# Vértices padronizados usuais de uma ETTJ de DI (rótulo -> deslocamento
# em (anos, meses) a partir da data de referência).
STANDARD_TENORS: dict[str, tuple[int, int]] = {
    "6M": (0, 6),
    "1A": (1, 0),
    "2A": (2, 0),
    "3A": (3, 0),
    "5A": (5, 0),
    "10A": (10, 0),
}


def _next_business_day(d: date) -> date:
    current = d
    while not is_business_day(current):
        current += timedelta(days=1)
    return current


def tenor_target_date(reference_date: date, years: float, months: int = 0) -> date:
    """Data-alvo de um tenor a partir de `reference_date`, ajustada para o
    próximo dia útil caso caia em fim de semana/feriado."""
    whole_years = int(years)
    extra_months = months + round((years - whole_years) * 12)
    target = reference_date + relativedelta(years=whole_years, months=extra_months)
    return _next_business_day(target)


def business_days_for_tenor(reference_date: date, years: float, months: int = 0) -> tuple[date, int]:
    """(data-alvo, dias úteis até ela) para um tenor a partir de `reference_date`."""
    target = tenor_target_date(reference_date, years, months)
    du = business_days_between(reference_date, target)
    return target, du


# -- Vértices padronizados ---------------------------------------------------


@dataclass(frozen=True, slots=True)
class VertexMetric:
    """Curva mapeada num vértice padronizado (ex.: "1A")."""

    label: str
    target_date: date
    business_days: int
    zero_rate: float
    discount_factor: float


def standardized_vertices(
    curve: ETTJCurve, tenors: dict[str, tuple[int, int]] | None = None
) -> list[VertexMetric]:
    """Mapeia a curva interpolada nos vértices padronizados (6M, 1A, 2A, ...)."""
    tenors = tenors or STANDARD_TENORS
    results: list[VertexMetric] = []
    for label, (years, months) in tenors.items():
        target, du = business_days_for_tenor(curve.trade_date, years, months)
        results.append(
            VertexMetric(
                label=label,
                target_date=target,
                business_days=du,
                zero_rate=curve.zero_rate(du),
                discount_factor=curve.discount_factor(du),
            )
        )
    return results


# -- Forwards -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ForwardMetric:
    """Taxa a termo discreta entre duas datas (ex.: "1A x 1A")."""

    label: str
    start_date: date
    end_date: date
    start_business_days: int
    end_business_days: int
    forward_rate: float


def forward_between(
    curve: ETTJCurve, start_years: float, tenor_years: float, label: str | None = None
) -> ForwardMetric:
    """Forward discreto entre `start_years` e `start_years + tenor_years`
    a partir da data de referência da curva (ex.: start_years=1, tenor_years=1
    -> forward "1A x 1A", a taxa de 1 ano negociada daqui a 1 ano)."""
    start_date, start_du = business_days_for_tenor(curve.trade_date, start_years)
    end_date, end_du = business_days_for_tenor(curve.trade_date, start_years + tenor_years)

    label = label or f"{_fmt_years(start_years)}x{_fmt_years(tenor_years)}"
    return ForwardMetric(
        label=label,
        start_date=start_date,
        end_date=end_date,
        start_business_days=start_du,
        end_business_days=end_du,
        forward_rate=curve.forward_rate(start_du, end_du),
    )


def _fmt_years(years: float) -> str:
    if years < 1:
        return f"{round(years * 12)}M"
    if years == int(years):
        return f"{int(years)}A"
    return f"{years:g}A"


@dataclass(frozen=True, slots=True)
class InstantaneousForwardPoint:
    business_days: int
    target_date: date
    forward_rate: float


def instantaneous_forward_curve(
    curve: ETTJCurve, tenors: dict[str, tuple[int, int]] | None = None
) -> list[InstantaneousForwardPoint]:
    """Taxa forward instantânea nos mesmos vértices padronizados, útil para
    visualizar a inclinação local da curva ponto a ponto."""
    tenors = tenors or STANDARD_TENORS
    results = []
    for _label, (years, months) in tenors.items():
        target, du = business_days_for_tenor(curve.trade_date, years, months)
        results.append(
            InstantaneousForwardPoint(
                business_days=du,
                target_date=target,
                forward_rate=curve.instantaneous_forward(du),
            )
        )
    return results


# -- Decomposição contra o Relatório Focus (prêmio de risco) ------------------


@dataclass(frozen=True, slots=True)
class RiskPremiumResult:
    """Decomposição da taxa de mercado (B3) contra a trajetória de Selic
    esperada pelo Focus no mesmo vencimento: o resíduo é o prêmio de risco
    (term premium) embutido no vértice longo da curva de DI."""

    label: str
    target_date: date
    business_days: int
    b3_zero_rate: float
    focus_implied_rate: float
    premium_bps: float


def focus_implied_rate(
    reference_date: date,
    target_date: date,
    focus_by_year: dict[int, FocusProjection],
) -> float:
    """Taxa anualizada (% a.a., base 252) implícita em compor a mediana Focus
    de Selic de cada ano-calendário entre `reference_date` e `target_date`,
    ponderada pelos dias úteis que cada ano contribui no intervalo.

    Aproxima a trajetória de política monetária que o mercado, em média,
    projeta para o período — a referência "livre de prêmio" contra a qual a
    taxa de mercado (que embute também prêmio de risco/liquidez) é comparada.
    """
    total_du = business_days_between(reference_date, target_date)
    if total_du <= 0:
        raise ValueError("target_date deve ser posterior a reference_date.")

    accumulated = 1.0
    segment_start = reference_date
    year = reference_date.year

    while True:
        year_end = date(year, 12, 31)
        segment_end = min(year_end, target_date)

        projection = focus_by_year.get(year)
        if projection is None:
            raise ValueError(f"Sem projeção Focus para o ano {year}.")

        segment_du = business_days_between(segment_start, segment_end)
        if segment_du > 0:
            accumulated *= (1 + projection.median / 100) ** (segment_du / BUSINESS_DAYS_PER_YEAR)

        if segment_end >= target_date:
            break
        segment_start = segment_end
        year += 1

    return (accumulated ** (BUSINESS_DAYS_PER_YEAR / total_du) - 1) * 100


def risk_premium_vs_focus(
    curve: ETTJCurve,
    focus_projections: list[FocusProjection],
    tenor_label: str = "10A",
    tenors: dict[str, tuple[int, int]] | None = None,
) -> RiskPremiumResult:
    """Compara a taxa zero da curva B3 no vértice `tenor_label` contra a
    taxa implícita na trajetória de Selic do Focus para o mesmo prazo."""
    tenors = tenors or STANDARD_TENORS
    if tenor_label not in tenors:
        raise ValueError(f"Vértice '{tenor_label}' não está em {sorted(tenors)}.")

    years, months = tenors[tenor_label]
    target_date, du = business_days_for_tenor(curve.trade_date, years, months)

    focus_by_year = {int(p.reference): p for p in focus_projections}
    implied = focus_implied_rate(curve.trade_date, target_date, focus_by_year)
    b3_rate = curve.zero_rate(du)

    return RiskPremiumResult(
        label=tenor_label,
        target_date=target_date,
        business_days=du,
        b3_zero_rate=b3_rate,
        focus_implied_rate=implied,
        premium_bps=(b3_rate - implied) * 100,
    )


DEFAULT_PREMIUM_TENOR_ORDER: tuple[str, ...] = ("10A", "5A", "3A", "2A", "1A")


def risk_premium_best_effort(
    curve: ETTJCurve,
    focus_by_year: dict[int, FocusProjection],
    tenor_order: tuple[str, ...] = DEFAULT_PREMIUM_TENOR_ORDER,
    tenors: dict[str, tuple[int, int]] | None = None,
) -> RiskPremiumResult | None:
    """Tenta `risk_premium_vs_focus` do vértice mais longo para o mais curto,
    usando o primeiro `tenor_label` com cobertura Focus completa ano a ano.

    O Focus costuma ter poucos (ou nenhum) respondentes para horizontes muito
    longos, então exigir sempre o vértice de 10A tornaria a decomposição
    frágil demais para uso ao vivo (API, terminal). Isso concentra a lógica
    de fallback que o script de validação e a API precisam ter em comum.
    """
    tenors = tenors or STANDARD_TENORS
    for label in tenor_order:
        if label not in tenors:
            continue
        years, months = tenors[label]
        target_date, _du = business_days_for_tenor(curve.trade_date, years, months)
        needed_years = set(range(curve.trade_date.year, target_date.year + 1))
        if not needed_years.issubset(focus_by_year.keys()):
            continue
        projections = [focus_by_year[y] for y in sorted(needed_years)]
        try:
            return risk_premium_vs_focus(curve, projections, tenor_label=label, tenors=tenors)
        except ValueError:
            continue
    return None
