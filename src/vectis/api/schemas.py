"""Modelos de resposta (Pydantic) da API. Só formato de saída — a lógica
de cálculo vive em `vectis.quant`; aqui só se decide o que trafega."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class IndicatorCard(BaseModel):
    key: str
    label: str
    value: float | None
    unit: str | None
    reference_date: date | None
    caption: str | None = None


class IndicatorsResponse(BaseModel):
    generated_at: datetime
    trade_date: date
    cards: list[IndicatorCard]


class VertexOut(BaseModel):
    code: str
    maturity: date
    business_days: int
    rate: float
    financial_volume: float
    contracts_traded: int


class InterpolatedPointOut(BaseModel):
    business_days: int
    date: date
    rate: float


class StandardVertexOut(BaseModel):
    label: str
    date: date
    business_days: int
    rate: float
    discount_factor: float


class ForwardOut(BaseModel):
    label: str
    start_date: date
    end_date: date
    rate: float


class InstantaneousForwardOut(BaseModel):
    date: date
    business_days: int
    rate: float


class ETTJResponse(BaseModel):
    trade_date: date
    vertices: list[VertexOut]
    interpolated: list[InterpolatedPointOut]
    standard_vertices: list[StandardVertexOut]
    forwards: list[ForwardOut]
    instantaneous_forward: list[InstantaneousForwardOut]


class SearchResult(BaseModel):
    type: str
    label: str
    value: float | None
    unit: str | None
    reference_date: date | None
    detail: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
