"""Camada de repositório: combina os clientes de API em consultas prontas
para consumo pelas próximas camadas (cards de indicadores, curva ETTJ).

Os clientes (SGS, Focus) não sabem nada sobre "cards" ou "curva" — essa
combinação de propósito fica isolada aqui, para que a origem dos dados
possa mudar sem afetar quem consome o repositório.
"""

from __future__ import annotations

from datetime import date, datetime

from .b3_di_client import B3DIClient
from .b3_di_parsers import InvalidDIContractCode, di_maturity_date
from .bcb_focus_client import BCBFocusClient
from .bcb_sgs_client import BCBSGSClient
from .calendar_br import business_days_between, latest_business_day
from .models import DIVertex, FocusProjection, MarketIndicators, TimeSeries
from .series_codes import IPCA_MENSAL, SELIC_EFETIVA_ANUALIZADA, SELIC_META

DEFAULT_MIN_CONTRACTS = 100
DEFAULT_MIN_FINANCIAL_VOLUME = 50_000_000.0


class MarketDataRepository:
    """Ponto único de acesso aos dados de mercado tratados."""

    def __init__(
        self,
        sgs_client: BCBSGSClient | None = None,
        focus_client: BCBFocusClient | None = None,
        di_client: B3DIClient | None = None,
    ) -> None:
        self._sgs = sgs_client or BCBSGSClient()
        self._focus = focus_client or BCBFocusClient()
        self._di = di_client or B3DIClient()

    # -- Séries históricas (base para cards pontuais e para a futura ETTJ) --

    def get_selic_meta_series(self, last_n: int = 30) -> TimeSeries:
        return self._sgs.get_series(SELIC_META, last_n=last_n)

    def get_selic_efetiva_series(self, last_n: int = 24) -> TimeSeries:
        return self._sgs.get_series(SELIC_EFETIVA_ANUALIZADA, last_n=last_n)

    def get_ipca_series(self, last_n: int = 24) -> TimeSeries:
        return self._sgs.get_series(IPCA_MENSAL, last_n=last_n)

    def get_focus_selic_median(self, reference_year: int | None = None) -> FocusProjection:
        return self._focus.get_annual_median(reference_year=reference_year)

    # -- Snapshot agregado, pronto para os cards de indicadores --

    def get_market_snapshot(self) -> MarketIndicators:
        selic_meta = self.get_selic_meta_series(last_n=1)
        selic_efetiva = self.get_selic_efetiva_series(last_n=1)
        ipca = self.get_ipca_series(last_n=1)
        focus_selic = self.get_focus_selic_median()

        if not (selic_meta.latest() and selic_efetiva.latest() and ipca.latest()):
            raise ValueError("Uma ou mais séries SGS retornaram vazias.")

        return MarketIndicators(
            selic_meta=selic_meta.latest(),
            selic_efetiva_anualizada=selic_efetiva.latest(),
            ipca_mensal=ipca.latest(),
            focus_selic=focus_selic,
            generated_at=datetime.now(),
        )

    # -- Curva de DI futuro (B3), base para o bootstrap/spline da ETTJ --

    def get_di_futures_curve(
        self,
        trade_date: date | None = None,
        min_contracts: int = DEFAULT_MIN_CONTRACTS,
        min_financial_volume: float = DEFAULT_MIN_FINANCIAL_VOLUME,
    ) -> list[DIVertex]:
        """Vértices líquidos da curva de DI futuro num pregão, ordenados por
        vencimento. Filtra contratos com liquidez insuficiente (ruído de
        pontas longas quase sem negociação) e já calcula o prazo em dias
        úteis até o vencimento — pronto para bootstrap/spline da ETTJ.
        """
        ref_date = latest_business_day(trade_date or date.today())
        rows = self._di.get_settlement_rows(ref_date)

        vertices: list[DIVertex] = []
        for row in rows:
            if not row.instrument.startswith("DI1"):
                continue
            if row.contracts_count < min_contracts:
                continue
            if row.financial_volume < min_financial_volume:
                continue

            try:
                maturity = di_maturity_date(row.instrument)
            except InvalidDIContractCode:
                continue

            du = business_days_between(ref_date, maturity)
            if du <= 0:
                continue

            vertices.append(
                DIVertex(
                    code=row.instrument,
                    maturity=maturity,
                    business_days_to_maturity=du,
                    settlement_rate=row.settlement_rate,
                    settlement_pu=row.settlement_pu,
                    contracts_traded=row.contracts_count,
                    financial_volume=row.financial_volume,
                    trade_date=ref_date,
                )
            )

        vertices.sort(key=lambda v: v.maturity)
        return vertices
