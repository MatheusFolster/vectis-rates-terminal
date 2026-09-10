"""Valida a camada de dados: busca as taxas oficiais do dia direto do BCB.

Uso:
    python scripts/validate_data_feed.py
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

    print("Consultando BCB SGS + Focus...\n")
    snapshot = repo.get_market_snapshot()

    print("=" * 60)
    print("VECTIS RATES TERMINAL — validação da camada de dados")
    print("=" * 60)

    print(f"\nSelic meta (Copom)         : {snapshot.selic_meta.value:.2f}%  "
          f"[{snapshot.selic_meta.date:%d/%m/%Y}]")
    print(f"Selic efetiva (mês, a.a.)  : {snapshot.selic_efetiva_anualizada.value:.2f}%  "
          f"[{snapshot.selic_efetiva_anualizada.date:%d/%m/%Y}]")
    print(f"IPCA (variação mensal)     : {snapshot.ipca_mensal.value:.2f}%  "
          f"[{snapshot.ipca_mensal.date:%m/%Y}]")

    focus = snapshot.focus_selic
    print(f"\nFocus Selic mediana {focus.reference}     : {focus.median:.2f}%  "
          f"(média {focus.mean:.2f}%, {focus.respondents} respondentes)")
    print(f"Focus apurado em           : {focus.reference_date:%d/%m/%Y}")

    print(f"\nSnapshot gerado em         : {snapshot.generated_at:%d/%m/%Y %H:%M:%S}")

    print("\n--- séries históricas (amostra p/ futura ETTJ) ---")
    selic_meta_series = repo.get_selic_meta_series(last_n=5)
    df = selic_meta_series.to_dataframe()
    print(df.to_string())

    print("\nOK: camada de dados operacional.")


if __name__ == "__main__":
    main()
