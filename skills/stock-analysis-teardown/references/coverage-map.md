# Coverage map

Who writes each playbook section, whether it is core, and which visuals usually work. Generated from `schema/coverage.json`, which is what `validate.py` reads.

| Id | Section | Owner | Core | Suggested visuals | Data to start from |
|---|---|---|---|---|---|
| 0.1 | Executive summary | verifier-editor | yes | exec-summary |  |
| 1.1 | Business model and revenue generation | part1-business | yes | text with columns (what it sells, who pays, how it earns); sankey of the income statement |  |
| 1.2 | Business segments and revenue breakdown | part1-business | yes | stacked-bar or stacked-100 of segment revenue; segmented-bar for geography or end market; text-chart |  |
| 1.3 | Competitive advantage and economic moat | part1-business | yes | cards (one per moat source, each with evidence and a durability tag) |  |
| 1.4 | Industry and sector analysis | part1-business | yes | bar of TAM by year (sourced, vendor flag if the source sells research); hbar of market share; text-chart |  |
| 1.5 | Pricing power and customer retention | part1-business | yes | matrix (differentiation vs switching cost, one point per product line); segmented-bar of customer concentration |  |
| 1.6 | Products and services, lifecycle and development | part1-business | no | timeline of launches; table of products with lifecycle stage |  |
| 1.7 | Key dependencies and operational risks | part1-strategy | yes | cards (dependency, exposure, impact, mitigation); table |  |
| 1.8 | Management, board and governance | part1-strategy | yes | cards (one per executive); table of pay mix from the DEF 14A; KPIs for insider ownership and board independence | DEF 14A in data/filings, insiders.json |
| 1.9 | Strategic threats and competitive risks | part1-strategy | yes | cards or a risk table with likelihood and impact (own view, marked basis view) |  |
| 1.10 | Mergers, acquisitions and strategic investments | part1-strategy | no | cards (one per deal with price, year, rationale, verdict); timeline | 8-Ks in filings/index.json, 10-K business combinations note |
| 1.11 | Growth strategy and geographic expansion | part1-strategy | no | cards; text-chart |  |
| 1.12 | Overall business quality assessment | verifier-editor | yes | scorecard (8 to 10 criteria, 1 to 5, each with a one-line reason) |  |
| 2.1 | Revenue performance and growth | part2-financials | yes | bar of revenue with annotations at inflection points; line of quarterly revenue | series revenue, revenue_growth; values revenue_cagr; quarterly revenue |
| 2.2 | Revenue mix and growth quality | part2-financials | no | stacked-100; segmented-bar | 10-K segment note and revenue disaggregation (extra_metrics) |
| 2.3 | Profitability and margins | part2-financials | yes | line of gross, operating, net margin; sankey | gross_margin, operating_margin, net_margin, normalized_operating_margin |
| 2.4 | Operating expenses and operating leverage | part2-financials | no | stacked-bar of opex; line of opex % revenue; bar of incremental operating margin | rnd, sga, opex_pct, core_opex_growth, incremental_operating_margin |
| 2.5 | Earnings quality and normalized profitability | part2-financials | yes | waterfall from GAAP to normalized; bar of SBC % revenue | normalized_operating_income, gain_on_divestiture, amort_intangibles, restructuring, sbc_pct_revenue, share_count_change |
| 2.6 | Cash flow generation and conversion | part2-financials | yes | bar with two series (net income vs free cash flow); line of FCF margin and FCF less SBC margin | cfo, fcf, fcf_margin, fcf_less_sbc, cfo_to_net_income, fcf_conversion |
| 2.7 | Working capital efficiency | part2-financials | no | line of DSO, DIO, DPO and CCC | dso, dio, dpo, ccc, operating_working_capital_pct_revenue |
| 2.8 | Balance sheet quality | part2-financials | no | kpis-chart; stacked-bar of asset mix | cash_and_investments, goodwill_intangibles_pct_assets, current_ratio, quick_ratio |
| 2.9 | Debt, liquidity and financial risk | part2-financials | yes | maturity-ladder; kpis-chart | total_debt, net_debt, net_debt_to_ebitda, interest_coverage, debt_to_equity, debt maturities |
| 2.10 | Capital expenditure and capital intensity | part2-financials | no | bar of capex; line of capex % revenue and capex to depreciation | capex, capex_pct_revenue, capex_to_depreciation, dna |
| 2.11 | Capital allocation | part2-financials | yes | stacked-bar of uses of cash (acquisitions, buybacks, dividends, debt repaid); KPIs of cumulative totals | cum_* values, buybacks, dividends_paid, acquisitions, debt_repaid, shares_diluted |
| 2.12 | Returns on capital and shareholder performance | part2-financials | yes | line of ROIC and ROIC normalized against WACC as a reference line; bar of diluted EPS | roic, roic_normalized, roe, roa, eps_diluted, shares_diluted, wacc |
| 2.13 | Financial peer benchmarking | part2-financials | yes | table from peers with heat; scatter growth vs EV/sales | peers.json |
| 2.14 | Financial outlook and key takeaways | part2-financials | yes | cards or text with two columns |  |
| 3.1 | Competitor analysis (playbook 1.13) | part3-competition | yes | table comparing products (sourced); matrix; cards per competitor |  |
| 3.2 | Ownership and insider activity (playbook 1.14) | part3-competition | yes | table of top holders (sourced, with date); KPIs from insiders.json; bar of buybacks | insiders.json, DEF 14A beneficial ownership table, buybacks series |
| 3.3 | Competitive pressures and brand strength (playbook 1.15) | part3-competition | no | cards; text-table |  |
| 4.1 | Multiples versus peers and own history | part4-valuation | yes | table; line of own EV/sales history; hbar of one multiple across peers | values pe_ttm, ev_ebitda_ttm, ev_sales_ttm, p_fcf_ttm, *_hist_avg, peer_median.* |
| 4.2 | DCF scenarios and sensitivity | part4-valuation | yes | table from scenarios; table from sensitivity | valuation.json |
| 4.3 | Reverse DCF: what the price assumes | part4-valuation | yes | kpis-chart; text | reverse_dcf_owner_fcf_cagr, reverse_dcf_revenue_cagr |
| 4.4 | Valuation summary (football field) | part4-valuation | yes | football-field | valuation.json football_field |
| 5.1 | Thesis and what would change my mind | verifier-editor | yes | thesis |  |

A slide may cover several ids (`"sections": ["2.6", "2.10"]`). An optional id left out goes in `meta.coverage_skipped` as `{"id": "2.7", "reason": "Software company with no inventory; working capital is two lines on slide fin-2"}`.
