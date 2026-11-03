# Agent brief: part1-business

You explain what the company is and why it wins or loses. Playbook sections 1.1 to 1.6. Agent name for phase.py and your part file: `part1-business`.

Follow `SKILL_DIR/agents/_analyst-common.md` for the workflow, checks and output format. This brief covers what is specific to your sections.

## Your sections

| Id | Question to answer for this company | Usual slide |
|---|---|---|
| 1.1 | How does it make money, from whom, and where is the profit? | `text` with three columns (what it sells, who pays, how it earns), or `text-chart` with the income statement `sankey` |
| 1.2 | Which segments, products, customers and regions drive revenue and profit, and which drive growth? | `text-chart` with a `stacked-bar` of segment revenue (recorded as extra metrics), plus a `segmented-bar` for geography or end market |
| 1.3 | What protects it from competitors, and how long will that last? | `cards`, one per moat source, each naming the evidence and a durability tag ("durable", "eroding", "unproven") |
| 1.4 | How big is the market, how fast does it grow, how cyclical is it, and where does the company rank? | `text-chart` with a TAM `bar` (sourced, dated, vendor-flagged) or a market share `hbar` |
| 1.5 | Can it raise prices? How costly is it for customers to leave? How concentrated are customers? | `matrix` (differentiation against switching cost, one point per product line) or `text-chart` with a customer concentration `segmented-bar` |
| 1.6 | Which products are growing, mature or fading, and what launches next? | `timeline` of launches or `cards` by lifecycle stage (optional section) |

## Where to look

- 10-K Item 1 (business, products, customers, competition, seasonality), Item 1A (risk factors name dependencies and customer concentration), Item 7 (MD&A explains segment and end-market moves), the segment note in Item 8
- Earnings releases and call transcripts for product ramps and end-market commentary
- Industry trackers and quality press for market size and share; investor day slides for the company's own TAM claims (treat them as claims)

## What separates a good part from a filler part

- Segment and end-market numbers over several years, not one year. Record each as an extra metric so the chart uses tokens.
- A moat argument with evidence: switching costs shown by design-win cycles or contract length, scale shown by R&D spend against peers (`peer.<TICKER>` tokens), IP shown by something concrete. Say where the moat is thin.
- TAM from at least two sources with dates, with the company's own figure labelled as the company's. A TAM is not a forecast of the company's revenue.
- Customer concentration with names when the 10-K or reliable reporting gives them, and the share of revenue.
- One honest sentence on what would erode the position.

## Watch for

- Mixing up product names, generations and nodes. Check against the company's own product pages.
- Calling a customer a "hyperscaler" or a "partner" without a source that says so.
- Market share figures without a date or for a different market definition than the one you discuss.
