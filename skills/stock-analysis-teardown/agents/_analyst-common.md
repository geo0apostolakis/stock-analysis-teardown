# How every analyst agent works

This applies to part1-business, part1-strategy, part2-financials, part3-competition and part4-valuation. Your own brief says which playbook sections you own and what good slides for them look like. Five analysts run at the same time, each on its own part, and none of you can see the others' work. The verifier-editor joins the parts afterwards.

You are given `RUN_DIR`, `SKILL_DIR` and the ticker. Use absolute paths. Scripts are `python3 SKILL_DIR/scripts/<name>.py`.

## 0. Start

```
python3 SKILL_DIR/scripts/phase.py RUN_DIR <your-agent-name> running
```

Read, in this order:

1. `RUN_DIR/data/fact-pack.md`, the briefing from the data-room agent
2. your sections in `SKILL_DIR/references/playbook.md` and `SKILL_DIR/references/coverage-map.md`
3. `SKILL_DIR/references/research-method.md`
4. `SKILL_DIR/references/writing-rules.md`
5. `SKILL_DIR/references/slide-layouts.md` (and `SKILL_DIR/schema/example-deck.json` for working JSON)
6. `RUN_DIR/data/financials.md` for the numbers

## 1. Plan

Write `RUN_DIR/notes/<agent>/plan.md` with the questions each of your sections must answer for this company, and a slide list: one line per slide with its id, sections, layout, chart kind and the claim its title will make. Scale to the company. A focused company may need one slide for two sections; a complex one may need two slides for one section. One idea per slide, so plan more slides with less on each rather than packing. Most parts land at 5 to 9 slides; Part 2 at 11 to 15.

## 2. Research

Follow `research-method.md`. Read the filings on disk first, then search the web. Log as you go in `notes/<agent>/research.md`. When you find a number the slides will use, record it with `metrics.py add` (see `metrics-definitions.md`) so it becomes a token, and keep its source in your source list.

Facts that change the story, such as a pending merger, a guidance cut or a CEO change, belong in your `findings` even if they sit outside your sections, because the other analysts cannot see your work.

## 3. Write the part

Write `RUN_DIR/parts/<agent>.json` in the format in `SKILL_DIR/references/run-folder.md`. Read "How a slide reads" in `writing-rules.md` first and copy that shape. For every slide:

- one idea, one chart or table (or none), three to five full-sentence bullets under 30 words each, the key phrase of each bullet in `**double asterisks**`, under 120 words of text in all

- an action title that states the claim, a kicker, and a takeaway
- `sections` listing the playbook ids it covers
- numbers as tokens, research facts with `refs`, own estimates with `"basis": "view"`
- a chart or table whenever the point is a number over time or a comparison; text-only slides only for qualitative points
- a `notes` field (not printed) with what you checked and any caveat

Then `findings` (three to six sentences the editor needs for the executive summary and thesis), `red_flags` and `open_questions`.

## 4. Check, fix, repeat

```
python3 SKILL_DIR/scripts/validate.py RUN_DIR --part parts/<agent>.json
```

Fix every error. For each warning, either fix it or say in the slide's `notes` why it stays. A part is finished when the check prints PASS. Then run `python3 SKILL_DIR/scripts/prepare.py RUN_DIR --deck RUN_DIR/parts/<agent>.json --out RUN_DIR/build/check-<agent>.json` and fix any "unknown metric" or "unknown series" error, which means a token key is misspelled.

## 5. Finish

```
python3 SKILL_DIR/scripts/phase.py RUN_DIR <your-agent-name> done
```

Reply with at most 15 lines: slides written, sections covered or skipped (with reasons), your findings, red flags, and anything you could not verify. Do not paste the JSON.

## Rules that are easy to break

- Never type a number that exists in metrics.json. Use the token. `metrics.py list RUN_DIR <word>` finds keys.
- Never attach a ticker to a company without checking it (`peers.json` or the SEC list).
- Never present an estimate as a fact. "No reliable public figure" is fine.
- Never use information dated after the as-of date in `run.json`.
- No em dashes, no "comprehensive" or "meticulous", no "by doing X and Y", no label colons. The checker will fail them.
- Never cram. A KPI row plus two charts plus bullets on one slide is three slides' worth. The validator fails more than five bullets, three KPIs, three blocks or 150 words on a slide.
