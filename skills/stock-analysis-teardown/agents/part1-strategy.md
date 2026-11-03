# Agent brief: part1-strategy

You judge the people, the risks and the strategy. Playbook sections 1.7 to 1.11. Agent name for phase.py and your part file: `part1-strategy`.

Follow `SKILL_DIR/agents/_analyst-common.md` for the workflow, checks and output format. This brief covers what is specific to your sections.

## Your sections

| Id | Question to answer for this company | Usual slide |
|---|---|---|
| 1.7 | What does it depend on (customers, suppliers, foundries, platforms, IP, partners), and what happens if one breaks? | `cards` or `text-table` with dependency, exposure, impact and mitigation |
| 1.8 | Who runs it, what is their record, how independent is the board, how are they paid, do they own stock? | `cards` for the CEO, CFO and one or two key executives; a `table` of pay mix from the proxy; KPIs for insider ownership and board independence |
| 1.9 | What could break the long-term position: competitors, new entrants, technology shifts, substitutes, regulation, geopolitics? | `cards` or a table with likelihood and impact (marked `"basis": "view"`) |
| 1.10 | What did it buy or sell, at what price, why, and did it work? Anything pending? | `cards` (one per deal: year, price, rationale, verdict) or a `timeline` |
| 1.11 | Where will growth come from: new markets, customers, products, regions? Organic or bought? What does it cost? | `cards` or `text-chart` |

## Where to look

- The proxy (`data/filings/DEF14A-*.txt`): executive bios, board independence, the summary compensation table, pay mix and performance metrics, beneficial ownership, related-party transactions
- `data/insiders.json` for open-market buys and sells by insiders (Form 4); sales under 10b5-1 plans mean less than open-market buys
- 10-K Item 1A risk factors, Item 7 for strategy, the business combinations and divestitures notes in Item 8
- `data/filings/index.json` for 8-Ks: deals (items 1.01, 2.01), executive changes (5.02)
- Merger documents (S-4, DEFM14A, the deal press release) for any pending transaction: price, structure, expected close, synergy claims, approvals
- Quality press and transcripts for management's track record against its own targets

## What separates a good part from a filler part

- A management record judged against what they promised: targets set at an investor day and what happened.
- Pay that is linked to the right things. Say what the bonus and the long-term awards pay for (revenue, EPS, TSR, ROIC) and whether that rewards value or size.
- For each big deal, the price paid against what was bought (revenue multiple), what was written off later (impairments), and whether it shows in growth today. Use the `acquisitions` and `goodwill` tokens.
- A pending deal treated as a major fact: what changes for the company if it closes and if it fails.
- Threats ranked, with the one that matters most named plainly.

## Watch for

- Confusing the CEO's previous employer achievements with this company's.
- Treating management's synergy estimates as facts.
- Insider sales that are routine (tax withholding on vesting, 10b5-1 plans) presented as a warning sign. Say which kind they are.
