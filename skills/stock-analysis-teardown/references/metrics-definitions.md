# Metric definitions

Every number in `data/metrics.json` is computed by `scripts/metrics.py` from SEC XBRL data (`statements.json`) and market data (`market.json`). This page says exactly how, so a reader can check any figure. Agents never compute a ratio in their heads. If a needed number is missing, record it with `metrics.py add` and a source.

Conventions. Money is in millions of the reporting currency. Percentages are stored as fractions (0.51 means 51%). Per-share values are in the reporting currency unless the key says otherwise. Fiscal years are labelled by the company's own fiscal year (`FY2026`), taken from the annual filing's `fy` field, so a year that ends in January 2026 is FY2026 for Marvell even though the SEC frame calls it CY2025.

## How to read a key

| Key form | Meaning | Example |
|---|---|---|
| `series@FY2026` | value for one fiscal year | `revenue@FY2026` |
| `series@TTM` | trailing twelve months, last fiscal year + year-to-date minus prior year-to-date | `fcf@TTM` |
| `series@LATEST` | latest balance sheet (most recent 10-Q or 10-K) | `net_debt@LATEST` |
| `revenue_growth@LATEST_Q_YOY` | latest quarter against the same quarter a year earlier | |
| `<series>_cagr`, `<series>_change` | over the display window (last five fiscal years, four steps) | `revenue_cagr` |
| `cum_<series>` | sum over the display window | `cum_buybacks` |
| `<multiple>_hist_avg` | average of fiscal-year-end multiples over the window | `ev_sales_hist_avg` |
| `peer.<TICKER>.<metric>` | a peer's value from `peers.json` | `peer.AVGO.gross_margin` |
| `peer_median.<metric>` | median across peers, company excluded | `peer_median.pe_ttm` |

`python3 scripts/metrics.py list RUN_DIR revenue` shows every key that contains "revenue" with its value.

## Income statement

| Series | Formula |
|---|---|
| revenue | Largest value across the revenue tags (Revenues, RevenueFromContractWithCustomer..., SalesRevenueNet, IFRS Revenue) |
| gross_profit | Reported; if the company does not report it, revenue minus cost of revenue |
| gross_margin | gross_profit / revenue |
| rnd, sga | Reported R&D and SG&A (SG&A = selling and marketing + G&A when reported apart) |
| core_opex | rnd + sga |
| total_opex | gross_profit minus operating_income (everything between the two lines) |
| other_opex | total_opex minus core_opex (amortization, restructuring, other) |
| opex_pct, rnd_pct, sga_pct | each divided by revenue |
| operating_margin | operating_income / revenue |
| incremental_operating_margin | change in operating income / change in revenue, year on year |
| normalized_operating_income | operating_income + amortization of acquired intangibles + restructuring + goodwill impairment. Only charges the filer tags on their own count. Charges booked inside cost of revenue (inventory write-downs, product claims, impairments of capitalized software) usually are not, so a year with large ones reads too low. Check the non-GAAP reconciliation in the earnings release and record a cleaner series with `metrics.py add` (for example `underlying_operating_margin@FY2025` = non-GAAP operating income minus SBC, over revenue) when it matters |
| dna | the larger of reported D&A and depreciation + amortization of acquired intangibles (some companies leave intangible amortization out of the D&A tag) |
| ebitda | operating_income + dna |
| adjusted_ebitda | ebitda + stock-based compensation |
| effective_tax_rate | income tax / pre-tax income (only when pre-tax income is positive) |
| net_margin | net_income / revenue |
| net_income_ex_divestiture_gain | net_income minus the gain on sale of a business taxed at 21% |
| eps_diluted | Reported diluted EPS, adjusted for later stock splits |
| share_count_change | change in diluted weighted shares, year on year |
| *_growth | (this year / last year) minus 1 |

## Cash flow

| Series | Formula |
|---|---|
| cfo | Net cash from operating activities |
| capex | Purchases of property and equipment (positive number) |
| fcf | cfo minus capex |
| fcf_margin | fcf / revenue |
| fcf_conversion | fcf / net_income (only when net income is positive) |
| cfo_to_net_income | cfo / net_income (only when net income is positive) |
| fcf_less_sbc, fcf_less_sbc_margin | fcf minus stock-based compensation, and that over revenue |
| owner_fcf@TTM | cfo minus capex minus SBC, trailing twelve months (the cash flow the DCF uses) |
| sbc_pct_revenue, sbc_pct_cfo | SBC over revenue, SBC over cfo |
| capex_pct_revenue, capex_to_depreciation | capex over revenue, capex over depreciation |
| shareholder_returns | buybacks + dividends paid |
| shareholder_returns_pct_fcf | shareholder_returns / fcf (only when fcf is positive) |

## Balance sheet and working capital

| Series | Formula |
|---|---|
| cash_and_investments | cash and equivalents + short-term investments |
| total_debt | long-term debt + short-term debt (current portion and commercial paper) |
| net_debt | total_debt minus cash_and_investments (negative means net cash) |
| net_debt_to_ebitda | net_debt / ebitda (only when EBITDA is positive) |
| debt_to_equity | total_debt / equity |
| interest_coverage | operating_income / interest expense |
| working_capital | current assets minus current liabilities |
| operating_working_capital | receivables + inventory minus payables |
| dso | receivables / revenue x 365 |
| dio | inventory / cost of revenue x 365 |
| dpo | payables / cost of revenue x 365 |
| ccc | dso + dio minus dpo |
| inventory_turnover | cost of revenue / inventory |
| current_ratio | current assets / current liabilities |
| quick_ratio | (cash_and_investments + receivables) / current liabilities |
| goodwill_intangibles_pct_assets | (goodwill + intangibles) / total assets |

Days measures use year-end balances, not averages, so they match how most filings discuss them.

## Returns

| Series | Formula |
|---|---|
| invested_capital | equity + total_debt minus cash_and_investments |
| nopat | operating_income x (1 minus tax rate). The tax rate is the effective rate kept between 0% and 35%, or 21% when the effective rate is missing |
| roic | nopat / average invested capital (this year and last) |
| roic_normalized | normalized_operating_income x (1 minus tax rate) / average invested capital |
| roe | net_income / average equity |
| roa | net_income / average total assets |

Compare ROIC with `wacc` from the valuation. A company earning below its cost of capital is shrinking value even while it grows.

## Market and valuation

| Key | Formula |
|---|---|
| price | last close from Yahoo Finance, in the listing currency |
| market_cap | price x shares outstanding from the latest filing cover page (all share classes); for ADRs, divided by the ADR ratio |
| enterprise_value | market cap (in reporting currency) + total_debt@LATEST minus cash_and_investments@LATEST |
| pe_ttm | market cap / net_income@TTM |
| ev_ebitda_ttm, ev_sales_ttm | enterprise value / ebitda@TTM, / revenue@TTM |
| p_fcf_ttm, fcf_yield_ttm | market cap / fcf@TTM, and its inverse |
| p_b | market cap / equity@LATEST |
| *_hist (series) | the same multiple at each fiscal year end, using that day's price and that year's numbers |
| beta | weekly returns against SPY over up to five years; `beta_adjusted` = 0.67 x beta + 0.33; `beta_used` is the beta in the cost of equity (the adjusted beta unless `valuation_inputs.json` overrides it) |
| return_1y / 3y / 5y | price change including dividends (adjusted close) |
| max_drawdown_5y | largest peak-to-trough fall in five years |
| risk_free_rate | US 10-year Treasury yield on the as-of date |

## Valuation (from `valuation.py`)

| Key | Meaning |
|---|---|
| wacc | cost of equity (risk-free + adjusted beta x ERP) and after-tax cost of debt, weighted by market cap and debt |
| dcf_<case>_per_share, dcf_<case>_upside | value per share in the bear, base and bull case, and the gap to the price |
| dcf_weighted_per_share | probability-weighted value |
| reverse_dcf_owner_fcf_cagr | the 10-year owner FCF growth rate that makes the DCF equal today's price |
| reverse_dcf_revenue_cagr | the revenue growth that implies, at the stated terminal owner FCF margin |

## Peer columns (from `peers.py`)

`market_cap_usd`, `revenue_ttm`, `revenue_growth` (TTM against the prior TTM), `revenue_cagr`, `gross_margin`, `operating_margin`, `net_margin`, `fcf_margin`, `roic`, `net_debt_to_ebitda`, `pe_ttm`, `ev_ebitda_ttm`, `ev_sales_ttm`, `p_fcf_ttm`, `fcf_yield`, `sbc_pct_revenue`. SEC filers are computed with the same code as the company. Peers that do not file with the SEC are entered by hand with `peers.py manual`, each value with a source.

## Numbers the code cannot compute

Segment revenue, customer concentration, backlog, guidance, non-GAAP figures, market share and anything from a transcript come from documents. Record each one so slides can use a token:

```
python3 scripts/metrics.py add RUN_DIR segment_dc_revenue@FY2026 6340 --unit money_m \
  --label "Data center revenue, FY2026" --source "10-K FY2026, segment note" --note "end-market table in Item 7"
```

The value lands in `data/extra_metrics.json` with its citation, appears in `metrics.json` at once and survives a recompute. Use the `@FY2026` style suffix so the key reads like the computed ones. The slide that prints it still carries `refs` to the source in your part's source list. Writes are locked, so parallel agents can add values safely.
