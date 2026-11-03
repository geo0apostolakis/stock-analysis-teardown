# Agent brief: part3-competition

You size up the competitors, the owners and the outside pressures. Playbook sections 3.1 to 3.3 (numbered 1.13 to 1.15 in the original plan). Agent name for phase.py and your part file: `part3-competition`.

Follow `SKILL_DIR/agents/_analyst-common.md` for the workflow, checks and output format. This brief covers what is specific to your sections.

Part 2 owns the financial peer table (2.13). You own the competitive story: products, pricing power, share, moves, owners and pressures. Use `peers.json` tokens for numbers, but do not rebuild the same table.

## Your sections

| Id | Question | Usual slides |
|---|---|---|
| 3.1 Competitor analysis | Who competes where (by product, customer segment, region)? Whose products are better or cheaper? Who has pricing power? What did competitors recently buy or partner on? What is the biggest competitive threat? | `text-table` comparing products or positions (sourced); `cards` per main competitor; `matrix` of positioning; an `hbar` of market share when a credible tracker gives one |
| 3.2 Ownership and insiders | Who are the big holders and are they adding or selling? What do insiders own, buy and sell? How big are buybacks, why, and did they create value? | `text-table` of top holders (from the proxy's beneficial ownership table or 13F-based sources, with dates); `kpis-chart` from `insiders.json` and `buybacks`, `shares_diluted` |
| 3.3 Pressures and brand (optional) | What regulatory, government and competitive pressure applies? How strong is the brand with customers? What do credible surveys say? | `cards` or `text-table` |

## Where to look

- The 10-K competition paragraph and risk factors name competitors and pressures
- Competitors' own 10-Ks, earnings calls and product pages for their side of the story; `data/peers/<TICKER>/` holds SEC peers' numbers
- Industry trackers and quality press for market share and design wins; the vendor flag matters here
- The proxy's "Security ownership of certain beneficial owners" table (holders above 5% with share counts and a date) and 13F-based holder pages for changes; date every holding
- `data/insiders.json` for Form 4 activity; the `buybacks`, `cum_buybacks` and `share_count_change` tokens for repurchases
- Regulators (export controls, antitrust reviews of pending deals), and surveys or customer studies from credible publishers

## What separates a good part from a filler part

- Competitors checked by name and ticker against `peers.json` or the SEC list. Two errors show up again and again in hand-built decks, a pair of competitors' tickers swapped and one peer's ROIC copied from another. The checker catches both, so avoid them in the first place.
- A clear statement of where the company is the leader, where it is the challenger, and where it is losing, with evidence.
- Ownership changes with dates and direction, not a static list.
- Buybacks judged against the share count. If the count still rises, buybacks only offset SBC; say so with `share_count_change` and `sbc`.
- Insider selling put in context (routine vesting sales and 10b5-1 plans against discretionary open-market sales). Open-market buys are rare and worth a line when they happen.

## Watch for

- Treating a company that is both a customer and a competitor (common in semiconductors and cloud) as only one of the two.
- Survey results from a vendor that sells to one side.
- Holder data older than six months presented as current.
