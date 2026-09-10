/* Vectis Rates Terminal — conecta os cards, o gráfico da ETTJ e a barra de
 * comando aos endpoints de vectis.api, e implementa toda a interatividade
 * (seleção de contrato/vértice, navegação por data de pregão). Sem
 * framework/build step: JS puro, servido como estático pelo FastAPI. */
(() => {
  "use strict";

  const fmtRate = (value, digits = 2) =>
    value === null || value === undefined
      ? "—"
      : value.toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits });

  const fmtInt = (value) => (value === null || value === undefined ? "—" : value.toLocaleString("pt-BR"));

  const fmtDate = (isoDate) => {
    if (!isoDate) return "—";
    const [y, m, d] = isoDate.split("-");
    return `${d}/${m}/${y}`;
  };

  const fmtDateTime = (isoDateTime) => {
    const dt = new Date(isoDateTime);
    if (Number.isNaN(dt.getTime())) return "—";
    return dt.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  };

  const DATE_FORMATS = [
    { re: /^(\d{2})\/(\d{2})\/(\d{4})$/, order: [3, 2, 1] }, // dd/mm/aaaa
    { re: /^(\d{4})-(\d{2})-(\d{2})$/, order: [1, 2, 3] }, // aaaa-mm-dd
    { re: /^(\d{2})-(\d{2})-(\d{4})$/, order: [3, 2, 1] }, // dd-mm-aaaa
  ];

  function tryParseISODate(text) {
    const trimmed = text.trim();
    for (const { re, order } of DATE_FORMATS) {
      const m = re.exec(trimmed);
      if (!m) continue;
      const [y, mo, d] = order.map((i) => m[i]);
      return `${y}-${mo}-${d}`;
    }
    return null;
  }

  async function fetchJSON(url) {
    const response = await fetch(url);
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || `Falha na requisição (${response.status})`);
    }
    return response.json();
  }

  // -- Estado global do terminal ---------------------------------------------

  const state = {
    latestTradeDate: null,
    currentTradeDate: null,
    curveData: null,
    selectedCode: null,
    selectedTenorLabel: null,
  };

  const chartRefs = { vertexEls: new Map(), tenorLineEls: new Map(), tenorLabelEls: new Map() };

  // -- KPI cards ------------------------------------------------------------

  const METRIC_ACCENT = {
    selic_meta: "var(--cx-primary)",
    selic_efetiva: "var(--accent-analytic)",
    ipca_mensal: "var(--cx-warning)",
    premio_risco: "var(--cx-warning)",
  };

  function renderIndicators(data) {
    const grid = document.getElementById("kpi-grid");
    grid.innerHTML = "";
    data.cards.forEach((card, i) => {
      const el = renderKpiCard(card);
      el.style.animationDelay = `${0.05 * i}s`;
      grid.appendChild(el);
    });

    document.getElementById("indicators-meta").textContent =
      `ÚLTIMA APURAÇÃO ${fmtDate(data.trade_date)} · ${fmtDateTime(data.generated_at)}`;
  }

  function renderKpiCard(card) {
    const el = document.createElement("article");
    el.className = "cx-metric";
    el.dataset.key = card.key;
    el.style.setProperty("--metric-accent", METRIC_ACCENT[card.key] || "var(--accent)");

    const label = document.createElement("div");
    label.className = "cx-metric__label";
    label.textContent = card.label;

    const value = document.createElement("div");
    const hasValue = card.value !== null && card.value !== undefined;
    value.className = "cx-metric__value" + (hasValue ? "" : " cx-metric__value--muted");
    if (card.key === "premio_risco" && hasValue) {
      value.classList.add(card.value >= 0 ? "cx-metric__value--negative" : "cx-metric__value--positive");
    }
    if (hasValue) {
      const digits = card.unit === "bps" ? 1 : 2;
      value.textContent = fmtRate(card.value, digits);
      if (card.unit) {
        const unit = document.createElement("span");
        unit.className = "cx-metric__unit";
        unit.textContent = card.unit;
        value.appendChild(unit);
      }
    } else {
      value.textContent = "sem dado";
    }

    const caption = document.createElement("div");
    caption.className = "cx-metric__caption";
    caption.textContent = card.caption || (card.reference_date ? `Ref. ${fmtDate(card.reference_date)}` : "");

    el.append(label, value, caption);
    return el;
  }

  function flashKpiCard(sgsLabel) {
    const match = /SGS\s+(\d+)/.exec(sgsLabel || "");
    if (!match) return;
    const codeToKey = { "432": "selic_meta", "4189": "selic_efetiva", "433": "ipca_mensal" };
    const key = codeToKey[match[1]];
    if (!key) return;
    const el = document.querySelector(`.cx-metric[data-key="${key}"]`);
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.classList.remove("is-flash");
    // força reflow para permitir reiniciar a animação em cliques repetidos
    void el.offsetWidth;
    el.classList.add("is-flash");
    setTimeout(() => el.classList.remove("is-flash"), 1200);
  }

  // -- Curva ETTJ (SVG desenhado à mão, sem lib de gráfico) ------------------

  const CHART_W = 960;
  const CHART_H = 380;
  const MARGIN = { top: 20, right: 24, bottom: 36, left: 56 };
  const SVG_NS = "http://www.w3.org/2000/svg";

  function svgEl(tag, attrs) {
    const node = document.createElementNS(SVG_NS, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    return node;
  }

  function setChartLoading(isLoading) {
    document.getElementById("chart-loading").hidden = !isLoading;
    document.getElementById("search-button").disabled = isLoading;
    document.getElementById("search-input").disabled = isLoading;
  }

  function updateLiveStatus() {
    const el = document.getElementById("live-status");
    const isLatest = !state.currentTradeDate || state.currentTradeDate === state.latestTradeDate;
    el.classList.toggle("cx-live--historic", !isLatest);
    el.innerHTML = isLatest
      ? '<i class="cx-live__dot"></i>TEMPO REAL'
      : '<i class="cx-live__dot"></i>PREGÃO CONSULTADO';
    document.getElementById("reset-date-btn").hidden = isLatest;
  }

  async function loadCurve(tradeDateISO) {
    setChartLoading(true);
    clearSelection();
    try {
      const url = tradeDateISO ? `/api/curve/ettj?trade_date=${encodeURIComponent(tradeDateISO)}` : "/api/curve/ettj";
      const data = await fetchJSON(url);
      state.curveData = data;
      if (!tradeDateISO) state.latestTradeDate = data.trade_date;
      state.currentTradeDate = data.trade_date;
      renderCurve(data);
      updateLiveStatus();
    } catch (err) {
      state.curveData = null;
      if (tradeDateISO) state.currentTradeDate = tradeDateISO;
      const empty = document.getElementById("chart-empty");
      empty.hidden = false;
      empty.textContent = err.message || "Erro ao carregar a curva ETTJ.";
      document.getElementById("ettj-chart").innerHTML = "";
      updateLiveStatus();
      console.error(err);
    } finally {
      setChartLoading(false);
    }
  }

  function renderCurve(data) {
    const svg = document.getElementById("ettj-chart");
    const empty = document.getElementById("chart-empty");
    svg.innerHTML = "";
    chartRefs.vertexEls.clear();
    chartRefs.tenorLineEls.clear();
    chartRefs.tenorLabelEls.clear();

    document.getElementById("chart-meta").textContent =
      `CURVA DI FUTURO B3 · BASE 252 · FECHAMENTO ${fmtDate(data.trade_date)}`;

    if (!data.interpolated || data.interpolated.length === 0) {
      empty.hidden = false;
      renderVertexChips([]);
      renderStandardChips([]);
      return;
    }
    empty.hidden = true;

    const plotW = CHART_W - MARGIN.left - MARGIN.right;
    const plotH = CHART_H - MARGIN.top - MARGIN.bottom;

    const duValues = data.interpolated.map((p) => p.business_days);
    const rateValues = data.interpolated.map((p) => p.rate).concat(data.vertices.map((v) => v.rate));
    const duMin = Math.min(...duValues);
    const duMax = Math.max(...duValues);
    const rateMin = Math.min(...rateValues);
    const rateMax = Math.max(...rateValues);
    const ratePad = Math.max((rateMax - rateMin) * 0.15, 0.05);
    const yLo = rateMin - ratePad;
    const yHi = rateMax + ratePad;

    const xScale = (du) => MARGIN.left + ((du - duMin) / (duMax - duMin || 1)) * plotW;
    const yScale = (rate) => MARGIN.top + plotH - ((rate - yLo) / (yHi - yLo || 1)) * plotH;

    const defs = svgEl("defs", {});
    const gradient = svgEl("linearGradient", { id: "curve-fill", x1: "0", y1: "0", x2: "0", y2: "1" });
    gradient.appendChild(svgEl("stop", { offset: "0%", "stop-color": "var(--cx-primary)", "stop-opacity": "0.22" }));
    gradient.appendChild(svgEl("stop", { offset: "100%", "stop-color": "var(--cx-primary)", "stop-opacity": "0" }));
    defs.appendChild(gradient);
    svg.appendChild(defs);

    // grade horizontal (taxa)
    const yTicks = 4;
    for (let i = 0; i <= yTicks; i++) {
      const rate = yLo + ((yHi - yLo) * i) / yTicks;
      const y = yScale(rate);
      svg.appendChild(svgEl("line", { x1: MARGIN.left, x2: CHART_W - MARGIN.right, y1: y.toFixed(2), y2: y.toFixed(2), stroke: "var(--border-default)", "stroke-width": 1 }));
      const label = svgEl("text", { x: MARGIN.left - 10, y: (y + 4).toFixed(2), "text-anchor": "end", class: "cx-mono", fill: "var(--text-muted)", "font-size": 11 });
      label.textContent = `${fmtRate(rate, 2)}%`;
      svg.appendChild(label);
    }

    // grade vertical (vértices padronizados) — clicável para selecionar o prazo
    for (const sv of data.standard_vertices) {
      if (sv.business_days < duMin || sv.business_days > duMax) continue;
      const x = xScale(sv.business_days);

      const hit = svgEl("rect", { x: (x - 8).toFixed(2), y: MARGIN.top, width: 16, height: plotH, class: "cx-chart-tenor-hit" });
      const line = svgEl("line", {
        x1: x.toFixed(2), x2: x.toFixed(2), y1: MARGIN.top, y2: MARGIN.top + plotH,
        stroke: "var(--border-default)", "stroke-width": 1, "stroke-dasharray": "3,4", class: "cx-chart-tenor-line",
      });
      const label = svgEl("text", { x: x.toFixed(2), y: CHART_H - 12, "text-anchor": "middle", class: "cx-mono cx-chart-tenor-label", fill: "var(--text-muted)", "font-size": 11 });
      label.textContent = sv.label;

      const onClick = () => selectTenor(sv.label);
      hit.addEventListener("click", onClick);
      label.addEventListener("click", onClick);

      svg.append(hit, line, label);
      chartRefs.tenorLineEls.set(sv.label, line);
      chartRefs.tenorLabelEls.set(sv.label, label);
    }

    // área preenchida sob a curva
    const baseline = MARGIN.top + plotH;
    const areaD =
      `M${xScale(data.interpolated[0].business_days).toFixed(2)},${baseline}` +
      data.interpolated.map((p) => `L${xScale(p.business_days).toFixed(2)},${yScale(p.rate).toFixed(2)}`).join(" ") +
      `L${xScale(data.interpolated[data.interpolated.length - 1].business_days).toFixed(2)},${baseline}Z`;
    svg.appendChild(svgEl("path", { d: areaD, fill: "url(#curve-fill)", stroke: "none" }));

    // linha da curva interpolada, com animação de desenho
    const pathD = data.interpolated
      .map((p, i) => `${i === 0 ? "M" : "L"}${xScale(p.business_days).toFixed(2)},${yScale(p.rate).toFixed(2)}`)
      .join(" ");
    const path = svgEl("path", { d: pathD, fill: "none", stroke: "var(--accent)", "stroke-width": 2.5, "stroke-linecap": "round", "stroke-linejoin": "round" });
    svg.appendChild(path);
    animateDraw(path);

    // vértices líquidos reais (pontos de mercado) — clicáveis, com tooltip
    const tooltip = document.getElementById("chart-tooltip");
    for (const v of data.vertices) {
      const cx = xScale(v.business_days);
      const cy = yScale(v.rate);
      const circle = svgEl("circle", { cx: cx.toFixed(2), cy: cy.toFixed(2), r: 4, class: "cx-chart-dot", fill: "var(--accent-analytic)", stroke: "var(--bg-canvas)", "stroke-width": 1.5 });
      circle.addEventListener("mouseenter", () => showTooltip(tooltip, v));
      circle.addEventListener("mousemove", (e) => positionTooltip(tooltip, e));
      circle.addEventListener("mouseleave", () => { tooltip.hidden = true; });
      circle.addEventListener("click", () => selectContract(v.code));
      svg.appendChild(circle);
      chartRefs.vertexEls.set(v.code, circle);
    }

    renderVertexChips(data.vertices);
    renderStandardChips(data.standard_vertices);
    renderStandardTable(data.standard_vertices);
    renderForwardsTable(data.forwards);
  }

  function animateDraw(path) {
    const length = path.getTotalLength();
    path.style.strokeDasharray = `${length}`;
    path.style.strokeDashoffset = `${length}`;
    path.getBoundingClientRect(); // força reflow antes da transição
    path.style.transition = "stroke-dashoffset 1s cubic-bezier(0.16,1,0.3,1)";
    requestAnimationFrame(() => { path.style.strokeDashoffset = "0"; });
  }

  function showTooltip(tooltip, vertex) {
    tooltip.innerHTML = "";
    const title = document.createElement("div");
    title.className = "cx-tooltip__title";
    title.textContent = `${vertex.code} · ${fmtRate(vertex.rate, 3)}% a.a.`;
    const detail = document.createElement("div");
    detail.className = "cx-tooltip__row";
    detail.textContent = `venc. ${fmtDate(vertex.maturity)} · ${vertex.business_days} du`;
    tooltip.append(title, detail);
    tooltip.hidden = false;
  }

  function positionTooltip(tooltip, event) {
    const wrap = document.querySelector(".cx-chart-wrap");
    const rect = wrap.getBoundingClientRect();
    tooltip.style.left = `${event.clientX - rect.left}px`;
    tooltip.style.top = `${event.clientY - rect.top}px`;
  }

  // -- Seleção: contrato DI1 (chip / ponto do gráfico / resultado de busca) --

  function selectContract(code, fallbackResult) {
    if (state.selectedCode === code) {
      clearContractSelection();
      return;
    }
    clearContractSelection();

    const vertex = state.curveData?.vertices?.find((v) => v.code === code);
    const record = vertex
      ? { ...vertex, illiquid: false }
      : fallbackResult
      ? {
          code,
          rate: fallbackResult.value,
          maturity: fallbackResult.reference_date,
          business_days: null,
          financial_volume: null,
          contracts_traded: null,
          illiquid: true,
        }
      : null;
    if (!record) return;

    state.selectedCode = code;

    const circle = chartRefs.vertexEls.get(code);
    if (circle) circle.classList.add("is-selected");

    document.querySelectorAll(`.cx-chip[data-code="${cssEscape(code)}"]`).forEach((chip) => chip.setAttribute("aria-pressed", "true"));

    renderFicha(record);
  }

  function clearContractSelection() {
    if (state.selectedCode) {
      const circle = chartRefs.vertexEls.get(state.selectedCode);
      if (circle) circle.classList.remove("is-selected");
      document.querySelectorAll(`.cx-chip[data-code="${cssEscape(state.selectedCode)}"]`).forEach((chip) => chip.setAttribute("aria-pressed", "false"));
    }
    state.selectedCode = null;
    document.getElementById("contract-ficha").hidden = true;
  }

  function selectTenor(label) {
    if (state.selectedTenorLabel === label) {
      clearTenorSelection();
      return;
    }
    clearTenorSelection();
    state.selectedTenorLabel = label;
    chartRefs.tenorLineEls.get(label)?.classList.add("is-selected");
    chartRefs.tenorLabelEls.get(label)?.classList.add("is-selected");
    document.querySelectorAll(`.cx-chip[data-tenor="${cssEscape(label)}"]`).forEach((chip) => chip.setAttribute("aria-pressed", "true"));
  }

  function clearTenorSelection() {
    if (state.selectedTenorLabel) {
      chartRefs.tenorLineEls.get(state.selectedTenorLabel)?.classList.remove("is-selected");
      chartRefs.tenorLabelEls.get(state.selectedTenorLabel)?.classList.remove("is-selected");
      document.querySelectorAll(`.cx-chip[data-tenor="${cssEscape(state.selectedTenorLabel)}"]`).forEach((chip) => chip.setAttribute("aria-pressed", "false"));
    }
    state.selectedTenorLabel = null;
  }

  function clearSelection() {
    clearContractSelection();
    clearTenorSelection();
  }

  function cssEscape(value) {
    return window.CSS && CSS.escape ? CSS.escape(value) : value.replace(/["\\]/g, "\\$&");
  }

  function renderFicha(record) {
    const ficha = document.getElementById("contract-ficha");
    ficha.innerHTML = "";

    const title = document.createElement("span");
    title.className = "cx-ficha__title";
    title.textContent = `${record.code} · ${fmtRate(record.rate, 3)}% a.a.`;
    ficha.appendChild(title);

    const fields = [
      ["Vencimento", fmtDate(record.maturity)],
      ["Dias úteis", record.business_days === null ? "—" : fmtInt(record.business_days)],
      ["Volume (R$ mi)", record.financial_volume === null ? "—" : fmtRate(record.financial_volume / 1_000_000, 1)],
      ["Contratos", record.contracts_traded === null ? "—" : fmtInt(record.contracts_traded)],
    ];
    for (const [label, value] of fields) {
      const field = document.createElement("div");
      field.className = "cx-ficha__field";
      field.innerHTML = `<span class="cx-ficha__field-label">${label}</span><span class="cx-ficha__field-value">${value}</span>`;
      ficha.appendChild(field);
    }

    if (record.illiquid) {
      const note = document.createElement("span");
      note.className = "cx-ficha__note";
      note.textContent = "Sem liquidez suficiente no pregão exibido — não plotado no gráfico.";
      ficha.appendChild(note);
    }

    const close = document.createElement("button");
    close.type = "button";
    close.className = "cx-ficha__close";
    close.setAttribute("aria-label", "Fechar ficha");
    close.textContent = "×";
    close.addEventListener("click", clearContractSelection);
    ficha.appendChild(close);

    ficha.hidden = false;
  }

  function renderVertexChips(vertices) {
    const container = document.getElementById("vertex-chips");
    container.innerHTML = "";
    for (const v of vertices.slice(0, 10)) {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "cx-chip";
      chip.textContent = v.code;
      chip.dataset.code = v.code;
      chip.setAttribute("aria-pressed", state.selectedCode === v.code ? "true" : "false");
      chip.title = `${fmtRate(v.rate, 3)}% a.a. · venc. ${fmtDate(v.maturity)}`;
      chip.addEventListener("click", () => selectContract(v.code));
      container.appendChild(chip);
    }
  }

  function renderStandardChips(standardVertices) {
    const container = document.getElementById("standard-chips");
    container.innerHTML = "";
    for (const sv of standardVertices) {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "cx-chip";
      chip.textContent = `${sv.label} · ${fmtRate(sv.rate, 2)}%`;
      chip.dataset.tenor = sv.label;
      chip.setAttribute("aria-pressed", state.selectedTenorLabel === sv.label ? "true" : "false");
      chip.addEventListener("click", () => selectTenor(sv.label));
      container.appendChild(chip);
    }
  }

  function renderStandardTable(rows) {
    const tbody = document.querySelector("#table-standard tbody");
    tbody.innerHTML = "";
    for (const row of rows) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${row.label}</td><td>${fmtDate(row.date)}</td><td>${row.business_days}</td><td>${fmtRate(row.rate, 3)}%</td>`;
      tbody.appendChild(tr);
    }
  }

  function renderForwardsTable(rows) {
    const tbody = document.querySelector("#table-forwards tbody");
    tbody.innerHTML = "";
    for (const row of rows) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${row.label}</td><td>${fmtDate(row.start_date)}</td><td>${fmtDate(row.end_date)}</td><td>${fmtRate(row.rate, 3)}%</td>`;
      tbody.appendChild(tr);
    }
  }

  function renderLegendPremium(indicatorsData) {
    const el = document.getElementById("legend-premium");
    const card = indicatorsData?.cards?.find((c) => c.key === "premio_risco");
    if (!card || card.value === null || card.value === undefined) {
      el.innerHTML = "Prêmio no vértice longo: <strong>—</strong>";
      return;
    }
    el.innerHTML = `Prêmio no vértice longo: <strong>${fmtRate(card.value, 1)} bps</strong>`;
  }

  // -- Busca ------------------------------------------------------------------

  function renderSearchResults(payload) {
    const container = document.getElementById("search-results");
    container.innerHTML = "";

    if (!payload.results || payload.results.length === 0) {
      container.hidden = false;
      const empty = document.createElement("div");
      empty.className = "cx-result__empty";
      empty.textContent = `Nenhum resultado para "${payload.query}".`;
      container.appendChild(empty);
      return;
    }

    container.hidden = false;
    for (const r of payload.results) {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "cx-result";

      const label = document.createElement("span");
      label.className = "cx-result__label";
      label.textContent = r.label;

      const detail = document.createElement("span");
      detail.className = "cx-result__detail";
      detail.textContent = r.detail;
      detail.title = r.detail;

      const value = document.createElement("span");
      value.className = "cx-result__value";
      value.textContent = r.value === null || r.value === undefined ? "—" : `${fmtRate(r.value, 2)}${r.unit ? " " + r.unit : ""}`;

      row.append(label, detail, value);
      row.addEventListener("click", () => applySearchResult(r));
      container.appendChild(row);
    }
  }

  function applySearchResult(result) {
    switch (result.type) {
      case "di_contract":
        selectContract(result.label, result);
        break;
      case "date":
        if (result.reference_date) loadCurve(result.reference_date);
        break;
      case "sgs_series":
        flashKpiCard(result.label);
        break;
      default:
        break;
    }
  }

  function debounce(fn, wait) {
    let handle;
    return (...args) => {
      clearTimeout(handle);
      handle = setTimeout(() => fn(...args), wait);
    };
  }

  async function runSearch(query) {
    const trimmed = query.trim();
    const container = document.getElementById("search-results");
    if (!trimmed) {
      container.hidden = true;
      container.innerHTML = "";
      return [];
    }
    try {
      const payload = await fetchJSON(`/api/search?q=${encodeURIComponent(trimmed)}`);
      renderSearchResults(payload);
      return payload.results || [];
    } catch (err) {
      container.hidden = false;
      container.innerHTML = `<div class="cx-result__empty">${err.message}</div>`;
      return [];
    }
  }

  async function handleSubmit(query) {
    const trimmed = query.trim();
    if (!trimmed) return;

    // uma data submetida recarrega a curva imediatamente, sem esperar clique
    // num resultado — o próprio texto já é a intenção completa da consulta.
    const isoDate = tryParseISODate(trimmed);
    if (isoDate) {
      await loadCurve(isoDate);
    }

    const results = await runSearch(trimmed);
    // evita recarregar a mesma data duas vezes quando o próprio texto
    // digitado já era a data (tratada acima) e o topo da busca é ela mesma.
    if (results.length > 0 && !(isoDate && results[0].type === "date")) {
      applySearchResult(results[0]);
    }
  }

  function setupSearch() {
    const input = document.getElementById("search-input");
    const button = document.getElementById("search-button");
    const debounced = debounce(() => runSearch(input.value), 300);

    input.addEventListener("input", debounced);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") handleSubmit(input.value);
    });
    button.addEventListener("click", () => handleSubmit(input.value));

    document.getElementById("reset-date-btn").addEventListener("click", () => loadCurve());
  }

  // -- Bootstrap ----------------------------------------------------------

  async function loadIndicators() {
    try {
      const data = await fetchJSON("/api/indicators");
      renderIndicators(data);
      renderLegendPremium(data);
    } catch (err) {
      document.getElementById("indicators-meta").textContent = "erro ao carregar indicadores";
      console.error(err);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    setupSearch();
    loadIndicators();
    loadCurve();
  });
})();
