"""Motor quantitativo do Vectis Rates Terminal.

Constrói a ETTJ a partir dos vértices líquidos de DI1 (camada
`vectis.data`) via spline cúbica monotônica (PCHIP/Fritsch-Carlson) e
expõe taxa zero, fatores de desconto, forwards e a decomposição do
prêmio de risco contra o Relatório Focus.

Módulos:
    interpolation: spline cúbica monotônica genérica (sem I/O).
    curve:         ETTJCurve — convenção DU/252, taxa zero, forwards.
    metrics:       vértices padronizados, forwards de mercado (ex.: 1Ax1A)
                   e decomposição contra o Focus (prêmio de risco).
"""

from .curve import BUSINESS_DAYS_PER_YEAR, CurvePoint, ETTJCurve
from .interpolation import MonotonicCubicSpline
from .metrics import (
    DEFAULT_PREMIUM_TENOR_ORDER,
    STANDARD_TENORS,
    ForwardMetric,
    InstantaneousForwardPoint,
    RiskPremiumResult,
    VertexMetric,
    business_days_for_tenor,
    focus_implied_rate,
    forward_between,
    instantaneous_forward_curve,
    risk_premium_best_effort,
    risk_premium_vs_focus,
    standardized_vertices,
    tenor_target_date,
)

__all__ = [
    "BUSINESS_DAYS_PER_YEAR",
    "CurvePoint",
    "ETTJCurve",
    "MonotonicCubicSpline",
    "DEFAULT_PREMIUM_TENOR_ORDER",
    "STANDARD_TENORS",
    "ForwardMetric",
    "InstantaneousForwardPoint",
    "RiskPremiumResult",
    "VertexMetric",
    "business_days_for_tenor",
    "focus_implied_rate",
    "forward_between",
    "instantaneous_forward_curve",
    "risk_premium_best_effort",
    "risk_premium_vs_focus",
    "standardized_vertices",
    "tenor_target_date",
]
