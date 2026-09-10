# Vectis Rates — Quant Terminal de Renda Fixa & Curva ETTJ

> Terminal analítico de inteligência quantitativa para precificação da Estrutura a Termo da Taxa de Juros (ETTJ) brasileira, extração de taxas a termo (forwards) e decomposição do prêmio de risco contra o consenso macroeconômico.

---

### 📌 Visão Geral & Problema de Mercado
No mercado financeiro brasileiro, a precificação da curva de juros soberana e dos contratos futuros de DI1 tradicionalmente depende de ferramentas proprietárias de alto custo (Bloomberg, Broadcast). 

O **Vectis Rates Terminal** elimina essa barreira consumindo dados oficiais diários da **B3** e do **Banco Central do Brasil (SGS e Olinda/Focus)** em uma estação de trabalho analítica, autônoma e interativa voltada para mesas de renda fixa e análise macroeconômica.

---

### ⚙️ Principais Diferenciais Técnicos & Quantitativos

- **Ingestão de Dados Oficiais & Resiliente:**
  - **B3 (Boletim de Derivativos):** Captura automatizada do fechamento de derivativos, extraindo entre 25 e 30 vértices líquidos de DI Futuro por pregão (taxa de ajuste, PU, número de contratos e volume financeiro em R$).
  - **Banco Central do Brasil (SGS & Focus):** Consulta direta às séries de Selic Meta (432), Selic Efetiva anualizada base 252 (4189), IPCA mensal (433) e projeções anuais de consenso de mercado via API OData Olinda.
  - **Calendário Nacional & ANBIMA:** Tratamento de feriados fixos e móveis nacionais (convenção dias úteis / 252).

- **Motor Quantitativo (`vectis.quant`):**
  - **Spline Cúbica Monotônica (PCHIP / Fritsch-Carlson):** Interpolação matemática da curva zero discreta, garantindo suavidade e impedindo overshoots ou oscilações artificiais nas taxas futuras.
  - **Taxas Forward:** Extração contínua da taxa instantânea e cálculo de forwards discretos padrão de mesa (1Ax1A, 2Ax1A, 2Ax3A, 5Ax5A).
  - **Decomposição do Prêmio de Risco:** Comparação entre a taxa spot negociada na B3 no vértice longo e a taxa acumulada esperada pelo Relatório Focus, apurando o prêmio de risco exigido em basis points (bps).

- **Interface Visual de Mesa Institucional:**
  - Identidade visual dark mode de alta precisão com acabamento em neon e partículas dinâmicas em canvas.
  - Gráfico da ETTJ renderizado em SVG puro, com destaque dinâmico de vértices e abertura de ficha técnica do contrato selecionado.
  - Navegação temporal com consulta histórica a pregões anteriores e recálculo da curva inteira em tempo real.

---

### 📂 Estrutura do Projeto

```text
vectis-rates-terminal/
├── src/vectis/
│   ├── data/          # Ingestão B3, BCB SGS, Focus e calendário DU/252
│   ├── quant/         # Spline PCHIP, cálculo da ETTJ, forwards e prêmio de risco
│   ├── api/           # Backend FastAPI, cache TTL em memória e rotas REST
│   └── web/           # Frontend (HTML5, CSS3, SVG, JavaScript puro)
├── scripts/
│   ├── run_terminal.py        # Inicialização do servidor local e abertura no navegador
│   ├── validate_data_feed.py  # Script de validação da camada de dados BCB
│   └── validate_ettj_engine.py# Validação e teste do motor quantitativo
└── requirements.txt
```

---

### 🚀 Como Executar Localmente

1. **Clone o repositório:**
```bash
git clone [https://github.com/MatheusFolster/vectis-rates-terminal.git](https://github.com/MatheusFolster/vectis-rates-terminal.git)
cd vectis-rates-terminal
```

2. **Instale as dependências:**
```bash
pip install -r requirements.txt
```

3. **Inicie o terminal:**
```bash
python scripts/run_terminal.py
```
A estação de trabalho abrirá automaticamente no navegador em `http://127.0.0.1:8000`.

---

### 🧭 Roadmap
- [x] Ingestão oficial B3 e BCB (SGS / Focus)
- [x] Motor de interpolação PCHIP e métricas de curva (DU/252)
- [x] Interface interativa em SVG e navegação histórica
- [ ] **Módulo Breakeven Inflation:** Curva real de NTN-B e projeção de inflação implícita
- [ ] Simulador de estresse e choques na curva de juros
- [ ] Hospedagem e deploy público em nuvem
