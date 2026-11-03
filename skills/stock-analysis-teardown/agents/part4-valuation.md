# Agent brief: part4-valuation

You answer "what does the price assume, and is that reasonable?" Sections 4.1 to 4.4. Agent name for phase.py and your part file: `part4-valuation`.

Follow `SKILL_DIR/agents/_analyst-common.md` for the workflow, checks and output format. This brief covers what is specific to valuation.

The teardown gives no Buy or Sell rating and no price target. It shows what the price implies and what different futures are worth, and leaves the decision to the reader.

## 1. Read the inputs

- `data/metrics.json` values: `price`, `market_cap`, `enterprise_value`, `pe_ttm`, `ev_ebitda_ttm`, `ev_sales_ttm`, `p_fcf_ttm`, `fcf_yield_ttm`, the `*_hist_avg` values, `owner_fcf@TTM`, `wacc`, `beta`, `risk_free_rate` (the cost of equity uses `beta_used`; `beta_adjusted` stays the Blume-adjusted regression beta)
- `data/peers.json` and the `peer_median.*` tokens
- guidance in the fact pack (`guide_*` extra metrics) and the latest earnings release
- consensus estimates for the next two fiscal years (revenue and EPS) from a reliable public page, dated, with the publisher flagged as vendor if it sells research

## 2. Set the assumptions

Open `data/valuation_inputs.json` (written by `valuation.py init` with neutral defaults) and replace every number with one you can defend. Write the reason next to each in the `*_reason` and `narrative` fields. If the TTM earnings hold a one-off gain or loss, record a clean EPS with `metrics.py add` and set `eps_key` to it, so the peer P/E bar of the football field is not built on the one-off. If preferred stock or other securities convert into common at no cost (the diluted EPS counts them), set `extra_shares_m` so per-share values, market cap and the reverse DCF all use the same share basis.

- **Bear, base, bull.** Ten-year paths for revenue growth and owner FCF margin (operating cash flow minus capex minus SBC, over revenue), and a probability for each. Tie year one and two to guidance and consensus, fade toward the industry's long-run growth, and set end margins against what the best peers earn today (`peer.<TICKER>.fcf_margin`) and the company's own history (`fcf_less_sbc_margin@FY...`).
- **ERP and terminal growth.** Keep the defaults unless you have a reason. Terminal growth above the risk-free rate is a red flag.
- **Reverse DCF terminal margin.** The owner FCF margin the business could reach at maturity.
- **Analyst targets.** Low, mean, high and count from a dated public source if one exists, for the football field. Leave null if not.

Then run

```
python3 SKILL_DIR/scripts/valuation.py run RUN_DIR
```

and read `data/valuation.json`. Sanity checks before you write slides:

- WACC usually lands between 7% and 13% for a listed company. Outside that, find out why.
- Set `cost_of_debt` to what the company pays to borrow today: the rate on its newest loan or bond, or the straight-debt yield of its converts (a 0% to 3% coupon is paid for with an equity option, so it is not the cost of debt). Historical interest / debt understates it when debt is new, interest is capitalized or the converts carry low coupons, and `valuation.py` stops if that ratio is below the risk-free rate.
- When you compare the WACC with a borrowing rate, compare like with like and get the direction right. WACC blends equity and after-tax debt, so a WACC above the newest loan rate is not by itself too low. The test is the cost of equity: for a loss-making company with a beta near 2 it should sit well above its secured borrowing rate. Show the build on the slide (cost of equity, pre-tax and after-tax cost of debt, weights).
- If the terminal value is more than about 75% of the base case value, say so on the slide.
- The base case should be explainable in one sentence. If it needs a paragraph, simplify.
- Re-run after every change. Every number on your slides comes from tokens that this run writes.

## 3. Slides

| Id | Question | Usual slide |
|---|---|---|
| 4.1 | Is it cheap or expensive against peers and its own history? | `text-table` with a hand-made table of P/E, EV/EBITDA, EV/sales, P/FCF and FCF yield against `peer_median.*` and `*_hist_avg` tokens; or an `hbar` of one multiple across peers; `line` of `ev_sales_hist` |
| 4.2 | What is it worth in each future? How sensitive is that to WACC and terminal growth? | `text-table` with `"from": "scenarios"`; `table` with `"from": "sensitivity"` |
| 4.3 | What growth does today's price require? Is that plausible? | `kpis-chart` or `text` with `reverse_dcf_owner_fcf_cagr` and `reverse_dcf_revenue_cagr`, compared with history (`revenue_cagr`), guidance and industry growth |
| 4.4 | Where does the price sit across all methods? | `chart` with the `football-field` |

Hand-made tables still use tokens in their cells (`"{{m:pe_ttm|x}}"`, `"{{m:peer_median.pe_ttm|x}}"`), so they need refs only for consensus or analyst numbers.

## What separates a good part from a filler part

- The reverse DCF is the centre. "The price needs owner FCF to grow 44% a year for ten years" is the sentence a reader remembers. Compare it with what the company has done and what the industry can support.
- Scenario narratives that name the drivers (a product ramp, a margin level, a customer win or loss), not just faster or slower growth.
- Multiples read with care. A high P/E on depressed GAAP earnings may be fine; say what normalizes it.
- An honest verdict input for the editor in `findings`: is the price asking for the bull case, the base case, or less?

## Watch for

- Mixing currencies (ADRs, foreign listings). Per-share values are in the price currency; the script handles FX, so use its tokens.
- A pending merger. If one is announced, value the company as it stands and say in a bullet how the deal would change the picture.
- Using analyst targets as evidence of value. They are a range on the football field, nothing more.
