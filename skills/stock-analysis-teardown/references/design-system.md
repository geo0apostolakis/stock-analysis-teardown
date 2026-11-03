# Design system

Light editorial. The deck should read like a well-set research note, not a sales pitch. Paper, ink and one accent. The design lives in `renderer/templates/deck.css` and `renderer/charts.js`; this page explains the choices so the designer agent can judge a slide and fix it in `deck.json` without touching the code.

## Colour

| Token | Hex | Use |
|---|---|---|
| paper | `#F6F3EC` | page background |
| ink | `#15140F` | titles, values, table text |
| ink-2 | `#4A4740` | body text, labels |
| muted | `#8B877D` | axis labels, footers, notes |
| rule | `#D8D2C4` | hairlines and dividers |
| primary | `#1F5FAE` | the company, the main series, kickers and accents |
| secondary | `#D9622B` | second series |
| tertiary | `#1B9E77` | third series |
| grey | `#B9B3A6` | peers and comparison series |
| positive / negative | `#2F7A3E` / `#B23B2E` | waterfall steps and KPI tone dots only |

The categorical order (primary, secondary, tertiary) was checked with a colour-vision-deficiency validator against the paper colour. Use the roles in that order and never invent a fourth hue. A fifth series folds into "Other" or moves to a second chart. Positive and negative are reserved for direction (up and down steps, good and bad KPIs) and always come with words.

## Type

- **Source Serif 4** (600) for titles, card headings, the verdict and big numerals on dividers.
- **Inter** (400 to 700) for everything else, with tabular figures in tables, KPIs and charts so digits line up.
- Title 40px (shrinks to 32px to stay on two lines), lead 21px, bullets 20px, plain text 23px (never below 19px), KPI values 44px, chart text 13 to 14px, footer 12.5px.
- Both fonts are embedded (SIL Open Font License, see `renderer/fonts/`). Nothing loads from the network.

## Grid

1600 x 900 pages with 72px side margins and a 50px top margin. A header block (kicker, title, lead), a flexible body, an optional "Bottom line" band and a footer with the ticker, date, cited sources and page number. Body columns are a 470px text column next to a flexible chart, or equal columns with 48 to 56px gaps.

## Charts

The rules come from a data-visualisation method that treats charts as something to check, not decorate.

- One y-axis. Never a dual-axis chart. Two measures on different scales get two charts or a common index.
- Bars are at most 24px thick with 4px rounded ends at the data end, square at the baseline.
- Lines are 2px with 8px end dots ringed in the paper colour.
- Grid lines are hairlines, axes are quiet, there is no chart border.
- Highlight the company in primary and grey the peers. Colour follows the entity, never its rank.
- A legend appears for two or more series. One series needs no legend because the title names it.
- A PDF has no hover, so single-series bar charts with up to eight bars print their values, and line charts label their last point.
- Text in charts is ink, never the series colour.

## What the designer may change

The designer works on `deck.json` only.

- Pick a better layout for a slide (`text-chart` to `kpis-chart`, `cards` to `timeline`).
- Pick a better chart kind for the job (see the table in `slide-layouts.md`). Swap a crowded `line` for `two-charts`, a 10-bar `bar` for an `hbar`.
- Split a crowded slide into two, or merge two thin slides that make the same point.
- Split or shorten any slide whose text overflows or reads as a wall of small type. Keep the meaning and every token and ref.
- Move a chart to `chart_side: "left"` to vary the rhythm when several text-chart slides run in a row.

The designer never changes a number, a token, a ref, a claim or the verdict. If a slide's content looks wrong, it goes back to the editor as a note in `build/design-notes.md`.

## What good looks like

- Every slide has one job and the title says what it is.
- The eye lands on the chart or the key number first, the bullets explain it.
- No slide is mostly empty and none is crammed. QA warnings about shrunk text are worth fixing.
- Runs of the same layout are broken up. Look at `build/shots/contact-sheet.png` for rhythm.
- Charts are big enough to read from across a table (at least 300px tall).
