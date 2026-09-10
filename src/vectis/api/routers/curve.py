"""GET /api/curve/ettj — vértices reais e curva interpolada para o gráfico."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import services
from ..dependencies import get_repository
from ..schemas import (
    ETTJResponse,
    ForwardOut,
    InstantaneousForwardOut,
    InterpolatedPointOut,
    StandardVertexOut,
    VertexOut,
)
from ...data import MarketDataRepository
from ...data.b3_di_client import B3RequestError
from ...data.calendar_br import add_business_days
from ...quant import ETTJCurve
from ...quant.metrics import forward_between, instantaneous_forward_curve, standardized_vertices

router = APIRouter(prefix="/api", tags=["curve"])

_GRID_POINTS = 120
# (início em anos, tenor em anos) dos pares de forward exibidos no gráfico.
_FORWARD_SPECS: list[tuple[float, float]] = [
    (0.5, 0.5),
    (1.0, 1.0),
    (2.0, 1.0),
    (2.0, 3.0),
    (5.0, 5.0),
]


@router.get("/curve/ettj", response_model=ETTJResponse)
def get_ettj_curve(
    trade_date: date | None = Query(default=None, description="Pregão específico (YYYY-MM-DD); padrão: mais recente disponível."),
    repo: MarketDataRepository = Depends(get_repository),
) -> ETTJResponse:
    if trade_date is not None:
        try:
            vertices = repo.get_di_futures_curve(trade_date=trade_date)
        except B3RequestError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if not vertices:
            raise HTTPException(
                status_code=404,
                detail=f"Sem vértices líquidos de DI1 para {trade_date.isoformat()}.",
            )
        curve = ETTJCurve.from_di_vertices(vertices)
    else:
        try:
            snapshot = services.get_latest_curve_snapshot(repo)
        except ValueError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        vertices, curve = snapshot.vertices, snapshot.curve

    std_vertices = standardized_vertices(curve)
    inst_fwd = instantaneous_forward_curve(curve)

    forwards: list[ForwardOut] = []
    for start_years, tenor_years in _FORWARD_SPECS:
        try:
            fwd = forward_between(curve, start_years, tenor_years)
        except ValueError:
            continue
        forwards.append(
            ForwardOut(label=fwd.label, start_date=fwd.start_date, end_date=fwd.end_date, rate=round(fwd.forward_rate, 4))
        )

    return ETTJResponse(
        trade_date=curve.trade_date,
        vertices=[
            VertexOut(
                code=v.code,
                maturity=v.maturity,
                business_days=v.business_days_to_maturity,
                rate=v.settlement_rate,
                financial_volume=v.financial_volume,
                contracts_traded=v.contracts_traded,
            )
            for v in vertices
        ],
        interpolated=_interpolated_grid(curve),
        standard_vertices=[
            StandardVertexOut(
                label=v.label,
                date=v.target_date,
                business_days=v.business_days,
                rate=round(v.zero_rate, 4),
                discount_factor=round(v.discount_factor, 6),
            )
            for v in std_vertices
        ],
        forwards=forwards,
        instantaneous_forward=[
            InstantaneousForwardOut(date=p.target_date, business_days=p.business_days, rate=round(p.forward_rate, 4))
            for p in inst_fwd
        ],
    )


def _interpolated_grid(curve: ETTJCurve) -> list[InterpolatedPointOut]:
    """Amostra `_GRID_POINTS` pontos ao longo do domínio da curva, para
    desenhar uma linha suave no gráfico (o front não reimplementa a spline —
    só interpola linearmente entre estes pontos, já densos o bastante)."""
    lo, hi = curve.min_business_days, curve.max_business_days
    if hi <= lo:
        du_values = [lo]
    else:
        step = (hi - lo) / (_GRID_POINTS - 1)
        raw = [round(lo + i * step) for i in range(_GRID_POINTS)]
        seen: set[int] = set()
        du_values = [du for du in raw if not (du in seen or seen.add(du))]

    return [
        InterpolatedPointOut(
            business_days=du,
            date=add_business_days(curve.trade_date, du),
            rate=round(curve.zero_rate(du), 4),
        )
        for du in du_values
    ]
