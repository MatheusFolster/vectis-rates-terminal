"""GET /api/indicators — snapshot para os 4 cards de KPI do terminal."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from .. import services
from ..dependencies import get_repository
from ..schemas import IndicatorCard, IndicatorsResponse
from ...data import MarketDataRepository
from ...data.http_client import BCBRequestError
from ...quant import RiskPremiumResult

router = APIRouter(prefix="/api", tags=["indicators"])


@router.get("/indicators", response_model=IndicatorsResponse)
def get_indicators(repo: MarketDataRepository = Depends(get_repository)) -> IndicatorsResponse:
    try:
        snapshot = services.get_market_snapshot_cached(repo)
        curve_snapshot = services.get_latest_curve_snapshot(repo)
    except (ValueError, BCBRequestError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    premium = services.get_risk_premium(repo, curve_snapshot.curve)

    cards = [
        IndicatorCard(
            key="selic_meta",
            label="Selic Meta",
            value=snapshot.selic_meta.value,
            unit="% a.a.",
            reference_date=snapshot.selic_meta.date,
            caption="Meta definida pelo Copom",
        ),
        IndicatorCard(
            key="selic_efetiva",
            label="Selic Efetiva (anualizada)",
            value=snapshot.selic_efetiva_anualizada.value,
            unit="% a.a.",
            reference_date=snapshot.selic_efetiva_anualizada.date,
            caption="Acumulada no mês, base 252",
        ),
        IndicatorCard(
            key="ipca_mensal",
            label="IPCA Mensal",
            value=snapshot.ipca_mensal.value,
            unit="%",
            reference_date=snapshot.ipca_mensal.date,
            caption="Variação mensal do IPCA",
        ),
        _premium_card(premium),
    ]

    return IndicatorsResponse(
        generated_at=snapshot.generated_at,
        trade_date=curve_snapshot.trade_date,
        cards=cards,
    )


def _premium_card(premium: RiskPremiumResult | None) -> IndicatorCard:
    if premium is None:
        return IndicatorCard(
            key="premio_risco",
            label="Prêmio de Risco",
            value=None,
            unit="bps",
            reference_date=None,
            caption="Sem cobertura Focus suficiente para nenhum vértice padronizado.",
        )
    return IndicatorCard(
        key="premio_risco",
        label=f"Prêmio de Risco ({premium.label})",
        value=round(premium.premium_bps, 1),
        unit="bps",
        reference_date=premium.target_date,
        caption=f"B3 {premium.b3_zero_rate:.2f}% vs. Focus implícito {premium.focus_implied_rate:.2f}%",
    )
