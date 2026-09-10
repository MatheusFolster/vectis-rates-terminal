"""Valida o motor quantitativo (vectis.quant): ajusta a ETTJ sobre os
vértices líquidos reais de DI1 (B3) e imprime a curva interpolada,
vértices padronizados, forwards e a decomposição do prêmio de risco
contra o Relatório Focus (BCB).

Uso:
    python scripts/validate_ettj_engine.py
"""

from __future__ import annotations

import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vectis.data import MarketDataRepository  # noqa: E402
from vectis.data.models import FocusProjection  # noqa: E402
from vectis.quant import ETTJCurve  # noqa: E402
from vectis.quant.metrics import (  # noqa: E402
    STANDARD_TENORS,
    forward_between,
    instantaneous_forward_curve,
    risk_premium_best_effort,
    standardized_vertices,
)


def fetch_focus_years(repo: MarketDataRepository, start_year: int, end_year: int) -> list[FocusProjection]:
    """Busca a mediana Focus ano a ano; anos sem projeção disponível são
    simplesmente omitidos (o Focus costuma ter poucos respondentes para
    horizontes muito longos, mas isso não deve interromper o restante)."""
    projections: list[FocusProjection] = []
    for year in range(start_year, end_year + 1):
        try:
            projections.append(repo.get_focus_selic_median(reference_year=year))
        except Exception:
            continue
    return projections


def print_header(title: str) -> None:
    print(f"\n-- {title} --")


def main() -> None:
    repo = MarketDataRepository()

    print("Consultando boletim de derivativos da B3...")
    di_vertices = repo.get_di_futures_curve()
    if not di_vertices:
        print("Nenhum vértice líquido encontrado — verifique se houve pregão na data.")
        return

    curve = ETTJCurve.from_di_vertices(di_vertices)

    print("=" * 84)
    print(f"VECTIS QUANT — ETTJ ajustada por spline cúbica monotônica (PCHIP)")
    print(f"Pregão: {curve.trade_date:%d/%m/%Y}   Convenção: dias úteis / 252")
    print("=" * 84)
    print(
        f"{len(di_vertices)} vértices líquidos de DI1 usados no ajuste "
        f"({curve.min_business_days} a {curve.max_business_days} du)."
    )

    # -- Vértices líquidos de entrada (insumo da spline) --
    print_header("Vértices líquidos de DI1 (insumo da spline)")
    header = f"{'Código':<10}{'Vencimento':<14}{'DU':>6}{'Taxa ajuste':>14}"
    print(header)
    print("-" * len(header))
    for v in di_vertices:
        maturity_str = f"{v.maturity:%d/%m/%Y}"
        print(f"{v.code:<10}{maturity_str:<14}{v.business_days_to_maturity:>6}{v.settlement_rate:>13.3f}%")

    # -- Curva interpolada em vértices padronizados --
    print_header("Curva interpolada em vértices padronizados")
    header = f"{'Vértice':<8}{'Data':<14}{'DU':>6}{'Taxa zero (% a.a.)':>20}{'Fator desconto':>16}"
    print(header)
    print("-" * len(header))
    std_vertices = standardized_vertices(curve)
    for vm in std_vertices:
        date_str = f"{vm.target_date:%d/%m/%Y}"
        print(f"{vm.label:<8}{date_str:<14}{vm.business_days:>6}{vm.zero_rate:>19.3f}%{vm.discount_factor:>16.6f}")

    # -- Forward instantâneo nos mesmos vértices --
    print_header("Forward instantâneo (inclinação local da curva)")
    header = f"{'Vértice':<8}{'Data':<14}{'DU':>6}{'Forward inst. (% a.a.)':>24}"
    print(header)
    print("-" * len(header))
    inst_fwd = instantaneous_forward_curve(curve)
    for label, point in zip(STANDARD_TENORS, inst_fwd):
        date_str = f"{point.target_date:%d/%m/%Y}"
        print(f"{label:<8}{date_str:<14}{point.business_days:>6}{point.forward_rate:>23.3f}%")

    # -- Forwards discretos de mercado (NxM) --
    print_header("Forwards discretos de mercado")
    header = f"{'Termo':<10}{'Início':<14}{'Fim':<14}{'Taxa forward (% a.a.)':>23}"
    print(header)
    print("-" * len(header))
    forward_specs = [
        (0.5, 0.5),  # 6Mx6M
        (1.0, 1.0),  # 1Ax1A
        (2.0, 1.0),  # 2Ax1A
        (2.0, 3.0),  # 2Ax3A (implícita entre 2A e 5A)
        (5.0, 5.0),  # 5Ax5A
    ]
    for start_years, tenor_years in forward_specs:
        try:
            fwd = forward_between(curve, start_years, tenor_years)
        except ValueError:
            continue
        start_str = f"{fwd.start_date:%d/%m/%Y}"
        end_str = f"{fwd.end_date:%d/%m/%Y}"
        print(f"{fwd.label:<10}{start_str:<14}{end_str:<14}{fwd.forward_rate:>22.3f}%")

    # -- Decomposição contra o Relatório Focus (prêmio de risco) --
    print_header("Decomposição vs. Relatório Focus (prêmio de risco no vértice longo)")
    current_year = curve.trade_date.year
    max_years = max(years for years, _months in STANDARD_TENORS.values())
    focus_projections = fetch_focus_years(repo, current_year, current_year + max_years)
    focus_by_year = {int(p.reference): p for p in focus_projections}

    premium = risk_premium_best_effort(curve, focus_by_year)
    if premium is None:
        print("Sem cobertura Focus suficiente (ano a ano) para nenhum dos vértices padronizados.")
    else:
        print(f"Vértice: {premium.label} ({premium.target_date:%d/%m/%Y}, {premium.business_days} du)")
        print(f"  Taxa zero B3 (mercado):        {premium.b3_zero_rate:>8.3f}% a.a.")
        print(f"  Taxa implícita Focus (Selic):  {premium.focus_implied_rate:>8.3f}% a.a.")
        print(f"  Prêmio de risco (B3 - Focus):  {premium.premium_bps:>8.1f} bps")

    print("\nOK: motor quantitativo (vectis.quant) operacional.")


if __name__ == "__main__":
    main()
