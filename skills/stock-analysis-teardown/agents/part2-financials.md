# Agent brief: part2-financials

You read five years of numbers and explain what they say about the business. Playbook sections 2.1 to 2.14. Agent name for phase.py and your part file: `part2-financials`.

Follow `SKILL_DIR/agents/_analyst-common.md` for the workflow, checks and output format. This brief covers what is specific to your sections.

The numbers are already computed. Your job is to choose the ones that tell the story, show them well, and explain the why from the MD&A, earnings releases and calls. `RUN_DIR/data/financials.md` is your starting table; `python3 SKILL_DIR/scripts/metrics.py list RUN_DIR <word>` finds any key; `SKILL_DIR/references/metrics-definitions.md` gives every formula.

## Your sections and the usual slides

| Id | Question | Usual slide (series keys) |
|---|---|---|
| 2.1 | How fast has revenue grown, where did it turn, how much was bought? | `text-chart`, `bar` of `revenue` with annotations at inflections; `area` of quarterly revenue (`"periods": "quarterly"`) |
| 2.2 | What is the mix and how good is the growth (recurring, concentrated, visible)? | `stacked-100` of segment extra metrics; `segmented-bar` (optional section) |
| 2.3 | How have gross, operating and net margins moved and why? | `kpis-chart` + `line` of `gross_margin`, `normalized_operating_margin`, `operating_margin`; or the `sankey` |
| 2.4 | Does revenue grow faster than costs? | `stacked-bar` of `rnd`, `sga`; `line` of `opex_pct`; `incremental_operating_margin` |
| 2.5 | How far is GAAP profit from underlying profit? One-offs, amortization, SBC, dilution? | `waterfall` from GAAP to normalized; `bar` of `sbc_pct_revenue`; `share_count_change` |
| 2.6 | Does profit turn into cash? | `bar` with two series `net_income` and `fcf`; `line` of `fcf_margin` and `fcf_less_sbc_margin` |
| 2.7 | How efficient is working capital? | `line` of `dso`, `dio`, `dpo`, `ccc` (optional section) |
| 2.8 | What is the balance sheet made of? Goodwill risk? | `kpis-chart` with `cash_and_investments`, `goodwill_intangibles_pct_assets`, `current_ratio` (optional section) |
| 2.9 | How much debt, when due, how covered? | `kpis-chart` with `net_debt`, `net_debt_to_ebitda`, `interest_coverage` and a `maturity-ladder` |
| 2.10 | How capital-intensive is it? | `bar` of `capex` and `capex_pct_revenue` (optional section) |
| 2.11 | Where did the cash go? | `stacked-bar` of `acquisitions`, `buybacks`, `dividends_paid`, `debt_repaid`; KPIs of `cum_*` totals |
| 2.12 | Does it earn more than its cost of capital? Per-share growth? | `line` of `roic` and `roic_normalized` with `wacc` in the text; `bar` of `eps_diluted`; `shares_diluted` |
| 2.13 | How do the numbers compare with peers? | `table` from `peers` with `heat`; `scatter` from `peers` of `revenue_growth` against `ev_sales_ttm` |
| 2.14 | What are the inflection points, strengths, weaknesses, and what does it mean for valuation? | `cards` or two-column `text` |

Combine sections when the company is simple (2.7 and 2.8 often fit one slide; 2.10 can be a bullet in 2.6). Ten to fourteen slides is normal.

## What separates a good part from a filler part

- Every chart has a reason. A title like "Free cash flow doubled while net income swung on a one-off gain" tells the reader what to see.
- The why behind each move, cited to the MD&A or a call: price or volume, mix, a ramp, an acquisition, an inventory correction.
- GAAP and underlying shown side by side. If net income includes a divestiture gain, say so and show `net_income_ex_divestiture_gain`. If amortization of acquired intangibles depresses GAAP margins, show `normalized_operating_margin` too.
- SBC treated as a real cost. Show `fcf_less_sbc` next to `fcf`, and `share_count_change`.
- TTM and the latest quarter (`@TTM`, `revenue_growth@LATEST_Q_YOY`) next to the last fiscal year when the year is stale.
- ROIC compared with `wacc`. A business earning below its cost of capital destroys value as it grows.
- Peer comparisons that note differences in business model or accounting (fabless against integrated, different fiscal years, non-GAAP habits).

## Watch for

- Funding for a build or a deal. Record each source by status as its own metric: committed (cash, signed facilities, received prepayments), targeted (announced plans, facilities in talks) and no named source. Headlines give the amount not yet committed first; "no named source" is the smaller number and only holds if the targeted money closes, so say that next to it.
- A fiscal year label that does not match the calendar (Marvell's FY2026 ended in January 2026). Say it once in a slide note or kicker where it matters.
- Growth rates on tiny or negative bases. Say "turned positive" instead of printing a 900% growth rate.
- Mixing GAAP and non-GAAP numbers in one chart.
- Restated years. If the data-room caveats mention a restatement, use the restated figures and say so.
