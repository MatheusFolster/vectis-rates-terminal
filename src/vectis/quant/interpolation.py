"""Interpolação por spline cúbica com preservação de monotonicidade
(Fritsch-Carlson / PCHIP).

Implementado em numpy puro (sem scipy) porque o resultado precisa ser
diferenciável analiticamente — usamos a derivada da própria spline para
extrair a taxa forward instantânea em `vectis.quant.curve` — e porque o
ambiente do projeto não tem scipy instalado.

Diferente de uma spline cúbica "natural" (que minimiza curvatura global
e pode overshoot entre vértices muito espaçados, gerando forwards
negativos ou com oscilação errática), o PCHIP ajusta a tangente em cada
nó para nunca ultrapassar a variação local dos dados: se a curva de
juros é localmente crescente entre três vértices, a interpolação entre
eles também é. Isso é essencial para uma ETTJ, onde a curva de taxas
zero é usada para extrair forwards — uma spline que overshoot na taxa
zero produz forwards com "dentes de serra" sem significado econômico.
"""

from __future__ import annotations

from typing import Literal

import numpy as np

Extrapolate = Literal["flat", "cubic"]


class MonotonicCubicSpline:
    """Interpolante Hermite cúbico monotônico (algoritmo de Fritsch-Carlson).

    Recebe nós `x` estritamente crescentes e valores `y`, e ajusta uma
    tangente em cada nó que preserva a monotonicidade local dos dados
    (sem overshoot entre segmentos consecutivos). Fora do domínio
    [x[0], x[-1]], usa extrapolação plana por padrão (`extrapolate="flat"`),
    que é a convenção usual de mercado para taxas antes do primeiro
    vértice ou depois do último vértice líquido.
    """

    def __init__(self, x: np.ndarray, y: np.ndarray, extrapolate: Extrapolate = "flat") -> None:
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        if x.shape != y.shape or x.ndim != 1:
            raise ValueError("x e y devem ser vetores 1D de mesmo tamanho.")
        if x.shape[0] < 2:
            raise ValueError("São necessários ao menos 2 vértices para interpolar.")
        if np.any(np.diff(x) <= 0):
            raise ValueError("x deve ser estritamente crescente (sem vértices duplicados).")

        self._x = x
        self._y = y
        self._extrapolate = extrapolate
        self._h = np.diff(x)
        self._delta = np.diff(y) / self._h
        self._m = self._fitch_carlson_tangents()

    @property
    def x_min(self) -> float:
        return float(self._x[0])

    @property
    def x_max(self) -> float:
        return float(self._x[-1])

    def _fitch_carlson_tangents(self) -> np.ndarray:
        n = self._x.shape[0]
        delta = self._delta
        h = self._h
        m = np.zeros(n)

        if n == 2:
            m[:] = delta[0]
            return m

        # Nós internos: média harmônica ponderada quando os secantes vizinhos
        # concordam em sinal; zero (nó plano) num extremo local, evitando
        # que a curva "balance" em torno de um pico ou vale.
        for i in range(1, n - 1):
            d0, d1 = delta[i - 1], delta[i]
            if d0 == 0.0 or d1 == 0.0 or (d0 > 0) != (d1 > 0):
                m[i] = 0.0
            else:
                w1 = 2 * h[i] + h[i - 1]
                w2 = h[i] + 2 * h[i - 1]
                m[i] = (w1 + w2) / (w1 / d0 + w2 / d1)

        # Extremidades: estimativa não-centrada de 3 pontos, com correção
        # de forma (Fritsch-Carlson) para não introduzir overshoot na ponta
        # curta/longa da curva, onde há menos vértices de apoio.
        m[0] = self._endpoint_tangent(h[0], h[1], delta[0], delta[1]) if n > 2 else delta[0]
        m[-1] = self._endpoint_tangent(h[-1], h[-2], delta[-1], delta[-2]) if n > 2 else delta[-1]
        return m

    @staticmethod
    def _endpoint_tangent(h0: float, h1: float, d0: float, d1: float) -> float:
        m = ((2 * h0 + h1) * d0 - h0 * d1) / (h0 + h1)
        if (m > 0) != (d0 > 0) and m != 0.0:
            return 0.0
        if (d0 > 0) != (d1 > 0) and abs(m) > abs(3 * d0):
            return 3 * d0
        return m

    def _segment_index(self, x: np.ndarray) -> np.ndarray:
        idx = np.searchsorted(self._x, x, side="right") - 1
        return np.clip(idx, 0, self._x.shape[0] - 2)

    def __call__(self, x: float | np.ndarray) -> float | np.ndarray:
        scalar_input = np.isscalar(x)
        xq = np.atleast_1d(np.asarray(x, dtype=float))

        if self._extrapolate == "flat":
            xq_clamped = np.clip(xq, self.x_min, self.x_max)
        else:
            xq_clamped = xq

        idx = self._segment_index(xq_clamped)
        x0, x1 = self._x[idx], self._x[idx + 1]
        y0, y1 = self._y[idx], self._y[idx + 1]
        m0, m1 = self._m[idx], self._m[idx + 1]
        h = x1 - x0
        t = (xq_clamped - x0) / h

        h00 = 2 * t**3 - 3 * t**2 + 1
        h10 = t**3 - 2 * t**2 + t
        h01 = -2 * t**3 + 3 * t**2
        h11 = t**3 - t**2

        result = h00 * y0 + h10 * h * m0 + h01 * y1 + h11 * h * m1
        return float(result[0]) if scalar_input else result

    def derivative(self, x: float | np.ndarray) -> float | np.ndarray:
        """dy/dx no ponto `x`. Fora do domínio com extrapolação plana, a
        derivada é zero (consistente com um patamar constante de taxa)."""
        scalar_input = np.isscalar(x)
        xq = np.atleast_1d(np.asarray(x, dtype=float))

        out_of_bounds = (xq < self.x_min) | (xq > self.x_max)
        xq_clamped = np.clip(xq, self.x_min, self.x_max) if self._extrapolate == "flat" else xq

        idx = self._segment_index(xq_clamped)
        x0, x1 = self._x[idx], self._x[idx + 1]
        y0, y1 = self._y[idx], self._y[idx + 1]
        m0, m1 = self._m[idx], self._m[idx + 1]
        h = x1 - x0
        t = (xq_clamped - x0) / h

        dh00 = 6 * t**2 - 6 * t
        dh10 = 3 * t**2 - 4 * t + 1
        dh01 = -6 * t**2 + 6 * t
        dh11 = 3 * t**2 - 2 * t

        result = (dh00 * y0 + dh10 * h * m0 + dh01 * y1 + dh11 * h * m1) / h
        if self._extrapolate == "flat":
            result = np.where(out_of_bounds, 0.0, result)
        return float(result[0]) if scalar_input else result
