# Slide layouts and chart kinds

Slides are JSON (`schema/deck.schema.json`). Analysts write them in their part files, the editor assembles `deck.json`, `prepare.py` fills in the numbers and `renderer/render.mjs` draws the PDF. A complete working example of every layout is `schema/example-deck.json`.

Pages are 1600 x 900. Body text keeps a readable size and the renderer reports anything that overflows. When a slide does not fit, split it; do not cram.

## Common fields

The `//` comments below are for reading only. JSON files cannot contain them.

```json
{
  "id": "fcf",                       // unique, short, kebab-case
  "part": "part2",                   // cover | summary | part1 | part2 | part3 | part4 | thesis | appendix
  "sections": ["2.6"],               // playbook ids this slide covers (references/coverage-map.md)
  "layout": "text-chart",
  "kicker": "Part 2 · Cash flow",
  "title": "Free cash flow doubled in two years and now covers SBC four times",
  "lead": "Optional framing sentence.",
  "bullets": [ "plain string", {"lead": "Bold lead-in.", "text": "The rest.", "refs": ["S3"]} ],
  "takeaway": "The bottom-line sentence.",
  "refs": ["S1"],                    // sources for the slide as a whole (title, lead, takeaway)
  "notes": "Not printed. What you checked, caveats, open questions."
}
```

A bullet can also carry `"sub": ["...", "..."]` and `"basis": "view"` (the teardown's own estimate or threshold).

## Number tokens

`{{m:KEY}}` or `{{m:KEY|FORMAT}}` anywhere in text. `KEY` is a key in `data/metrics.json` values (see `references/metrics-definitions.md`; `python3 scripts/metrics.py list RUN_DIR <word>` shows what exists).

| Format | Prints | Use for |
|---|---|---|
| `money` (default for money) | $8.19B, $820M | prose |
| `money_m` / `money_b` / `money_b2` | $8,195M / $8.2B / $8.19B | when you need a fixed scale |
| `pct` / `pct1` / `pct2` | 51% / 51.0% / 51.04% | shares and margins |
| `pp` / `pp1` | +4 pp / +4.2 pp | differences of two percentages |
| `x` / `x0` / `x2` | 24.3x / 24x / 24.31x | multiples |
| `ps` / `ps0` | $3.07 / $3 | per-share amounts |
| `num` / `num1` / `num2` | 1,234 / 1,234.5 / 1.23 | counts, ratios |
| `days`, `shares` | 45 days, 870M shares | |
| add `+` | +42.1% | force a sign: `pct1+` |

In chart data and waterfall steps a bare token `"{{m:fcf@FY2026}}"` becomes the raw number.

## Layouts

### cover
Generated from `meta`. Optional `kpis` (four work best) and one `price` chart on the right.
```json
{"id": "cover", "part": "cover", "layout": "cover", "title": "Marvell Technology",
 "kpis": [{"label": "Share price", "value": "{{m:price|ps}}"}, {"label": "Market cap", "value": "{{m:market_cap|money}}"},
          {"label": "P/E, trailing", "value": "{{m:pe_ttm|x}}"}, {"label": "EV / sales, trailing", "value": "{{m:ev_sales_ttm|x}}"}],
 "charts": [{"kind": "price", "title": "Share price, five years", "events": [{"date": "2026-11-02", "label": "Lumentum deal announced"}], "source": "Yahoo Finance"}]}
```

### roadmap
Lists the dividers with page numbers automatically. Give it a title.

### divider
One per part. `kicker` ("Part 2"), `title`, optional `lead` and up to four `bullets` naming what the part covers.

### exec-summary
`kpis` (five), `strengths` (three) and `risks` (three) as bullets, plus `title` and `takeaway`. The verdict and quality score come from `meta`.

### text
`bullets` (one column; set `"bullet_columns": 2` for two), or `paragraphs`, or `columns` (two to four, each `{"heading", "bullets"}`). Optional `kpis` row on top.

### text-chart
Three to five bullets on the left, one chart on the right. `"chart_side": "left"` flips it. The workhorse layout and the default for most slides. A second chart only when the two are read together, and then cut the bullets to three.

### chart
One chart across the slide, optional short `bullets` in a narrow column on the right.

### two-charts
Exactly two charts side by side, at most three short `bullets` underneath. Use it only when the comparison is the point.

### kpis-chart
A row of up to three `kpis` on top, one chart below, optional short `bullets` on the right. Do not add a second chart.
```json
"kpis": [{"label": "FCF, FY2026", "value": "{{m:fcf@FY2026|money}}", "sub": "{{m:fcf_margin@FY2026|pct}} of revenue", "tone": "good"}]
```
`tone` is `good`, `bad` or `neutral`. It adds a small coloured dot before `sub`, so `sub` must say in words why it is good or bad.

### table
A table across the slide, optional `bullets` on the right. Tables come `from` the data or are written by hand.
```json
"table": {"from": "peers", "heat": true, "columns": ["revenue_growth", "gross_margin", "operating_margin", "roic", "pe_ttm", "ev_sales_ttm"]}
"table": {"from": "financials", "metrics": ["revenue", "revenue_growth", "gross_margin", "fcf", "roic"]}
"table": {"from": "sensitivity"}
"table": {"from": "scenarios"}
"table": {"columns": ["Holder", "Stake", "Change"], "rows": [["Vanguard", "8.9%", "+0.3 pp"]], "refs": ["S12"], "note": "13F filings as of 30 Jun 2026"}
```
Hand-made tables need `refs`. Keep to 10 rows or fewer and cells short. Columns that are mostly words align left and wrap; set `col_align` (`["left", "right", ...]`) to override.

### text-table
Bullets on the left, a table on the right.

### cards
Two to six cards (`tag`, `title`, `body`, `facts`, `refs`). Three or four read best. Good for M&A deals, executives, moat sources, competitors, risks.

### matrix
A 2x2 with labelled points, bullets on the right. Scores are 0 to 10.
```json
"matrix": {"x_label": "Customer switching cost", "y_label": "Product differentiation",
           "x_ends": ["Low", "High"], "y_ends": ["Low", "High"],
           "quadrants": ["Differentiated, easy to leave", "Pricing power", "Commodity", "Sticky but plain"],
           "points": [{"label": "Custom AI silicon", "x": 8.5, "y": 8, "highlight": true}]}
```
Point positions are the teardown's judgment. Explain them in the bullets.

### timeline
Up to five items in a row, six to ten in two columns. Each `{date, title, body, refs}`.

### scorecard
Criteria scored 1 to 5 in half steps with a one-line reason each. Used for 1.12. The overall score is `meta.quality_score`.

### thesis
`paragraphs` (two or three), `watchlist` (four to six "what would change my mind" signposts, each with a `lead` naming the metric and `text` giving the threshold).

### sources
Generated, and always the last slide. The source list paginates itself and each page carries a one-line not-investment-advice note, so there is no separate disclaimer page (the cover carries the note too). Inline source markers are off: `refs` print in the slide footer. Set `meta.inline_refs: true` only if a reader asks for markers next to each claim.

## Chart kinds

Every chart has a short `title` naming the measure and unit ("Revenue, $ millions"). Money axes print their own $M/$B/$T labels, so name the unit the axis will show: once any bar or running total reaches 1,000 (millions), write "$ billions" ("Cash, FY2026, $ billions"). `prepare.py` rewrites a wrong "millions" and warns. Each chart also takes optional `subtitle`, `source` and `refs`. Series use `metric` (a series key in metrics.json; years come from the display window) or `data` with `categories`. Roles colour the series: `primary` (the company or the main measure), `secondary`, `tertiary`, `muted` (comparison). Use them in that order.

| Kind | Use it for | Notes |
|---|---|---|
| `bar` | one measure over years, or a few categories | `highlight` a category to grey the rest; `annotations: [{at, text}]` |
| `stacked-bar` | parts of a total over time (segments, opex lines) | totals print on top |
| `stacked-100` | mix over time | shares print inside the first and last column |
| `line` | margins and ratios over time, two to four series | no dual axis, ever |
| `area` | one cumulative or volume series over time | `"periods": "quarterly"` for the last 12 quarters |
| `hbar` | ranking across companies or products | sorted, `highlight` the company |
| `waterfall` | bridges: GAAP to normalized, net income to FCF, opening to closing cash | `steps: [{label, value, total?}]`, a step with `total: true` and no value prints the running total. Give the closing total its filed value when there is one, so `prepare.py` can check the steps add up to it. In a bridge between two balances at or above zero (cash, debt), put the inflows before the outflows: operating cash flow and financing first, then capex and acquisitions. Following the cash flow statement order (operating, investing, financing) makes the running total dip below zero and draws a cash balance that never existed; `prepare.py` stops on it. Fold steps under 1% of the range (FX, rounding) into a neighbour |
| `sankey` | where revenue goes | `"from": "income_statement"`, optional `period` |
| `scatter` | growth against valuation across peers | `"from": "peers", "x_metric": "revenue_growth", "y_metric": "ev_sales_ttm"` |
| `football-field` | valuation ranges against the price | data from valuation.json |
| `maturity-ladder` | debt due by year | data from the 10-K debt note |
| `price` | share price over five years | `events: [{date, label}]` numbered on the chart; `"benchmark": true` indexes against SPY |
| `segmented-bar` | one total split into a few parts (customer concentration, geography) | `parts: [{label, value, role?}]`, `"unit": "pct"`, `"of_total": true` when values are already shares |

Two measures on different scales never share a chart. Use `two-charts`, or index both to 100.
