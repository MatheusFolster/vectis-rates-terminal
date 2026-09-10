"""Camada de dados do Vectis Rates Terminal.

Expõe as peças públicas do pacote: repositório agregador, clientes de
API individuais e os modelos tratados que trafegam entre camadas.
"""

from .b3_di_client import B3DIClient
from .bcb_focus_client import BCBFocusClient
from .bcb_sgs_client import BCBSGSClient
from .models import DIVertex, FocusProjection, MarketIndicators, SeriesPoint, TimeSeries
from .repository import MarketDataRepository

__all__ = [
    "B3DIClient",
    "BCBFocusClient",
    "BCBSGSClient",
    "DIVertex",
    "FocusProjection",
    "MarketDataRepository",
    "MarketIndicators",
    "SeriesPoint",
    "TimeSeries",
]
