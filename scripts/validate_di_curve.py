"""Valida a ingestão da B3: baixa e imprime os vértices líquidos de DI1.

Uso:
    python scripts/validate_di_curve.py
"""

from __future__ import annotations

import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vectis.data import MarketDataRepository  # noqa: E402


def main() -> None:
    repo = MarketDataRepository()

    print("Consultando boletim de derivativos da B3...\n")
    vertices = repo.get_di_futures_curve()

    if not vertices:
        print("Nenhum vértice líquido encontrado — verifique se houve pregão na data.")
        return

    ref_date = vertices[0].trade_date
    print("=" * 78)
    print(f"VECTIS RATES TERMINAL — curva de DI futuro (B3), pregão {ref_date:%d/%m/%Y}")
    print("=" * 78)

    header = f"{'Código':<10}{'Vencimento':<14}{'DU':>6}{'Taxa ajuste':>14}{'PU ajuste':>14}{'Contratos':>13}{'Volume (R$ mi)':>17}"
    print(header)
    print("-" * len(header))

    for v in vertices:
        maturity_str = f"{v.maturity:%d/%m/%Y}"
        rate_str = f"{v.settlement_rate:.3f}%"
        print(
            f"{v.code:<10}{maturity_str:<14}{v.business_days_to_maturity:>6}"
            f"{rate_str:>14}{v.settlement_pu:>14,.2f}"
            f"{v.contracts_traded:>13,}{v.financial_volume / 1_000_000:>17,.1f}"
        )

    print("-" * len(header))
    print(f"{len(vertices)} vértices líquidos (filtro de liquidez aplicado).")
    print("\nOK: ingestão de DI futuro (B3) operacional.")


if __name__ == "__main__":
    main()
