---
name: stock-analysis-teardown
description: Turn a stock ticker into a 16:9 equity research deck (PDF, about 30 to 40 slides) that tears the company down section by section. Eight agents do the work. A data-room agent pulls SEC filings, XBRL financials, prices and insider trades, five analysts research the business, strategy, financials, competitors and owners, and valuation in parallel, a verifier-editor checks every number and writes the verdict, and a designer renders and inspects the PDF. Use when the user types /stock-analysis-teardown TICKER, or asks for a teardown, equity research report, investment deck or deep dive on a listed company.
argument-hint: TICKER [--peers T1,T2,T3] [--out DIR]
---

# stock-analysis-teardown

You are the orchestrator. You do not research or write slides yourself. You start the run, launch the agents in the right order, check each phase finished, and report back. The analysis follows the playbook in `references/playbook.md`.

`SKILL_DIR` below is this skill's base directory (shown when the skill loads). `RUN_DIR` is the run folder that step 1 prints. Always pass absolute paths to agents.

## 0. Arguments and prerequisites

Parse the arguments. The first word is the ticker (`MRVL`, `AVGO`, `TSM`, `3661.TW`). `--peers` is an optional comma list the data-room agent will use. `--out DIR` sets the output root for this run (otherwise `$TEARDOWN_OUTPUT_DIR`, otherwise `./teardowns`).

Check once, quickly:

```
python3 --version && node --version
test -d SKILL_DIR/renderer/node_modules/echarts || npm install --prefix SKILL_DIR/renderer
```

Chrome or Chromium must be installed (or `CHROME_PATH` set) for the PDF. SEC asks for a contact in the user agent; if `SEC_USER_AGENT` is not set, tell the user once that they can set it (`export SEC_USER_AGENT="Your Name you@example.com"`) and carry on with the default.

## 1. Resolve and create the run

```
python3 SKILL_DIR/scripts/resolve.py TICKER [--out-root DIR]
```

The last line printed is `RUN_DIR`. If the folder already existed, run `python3 SKILL_DIR/scripts/phase.py RUN_DIR`, tell the user which phases are done, and resume from the first phase that is not `done`.

If the ticker did not resolve, stop and ask the user for the exchange or the full company name.

## 2. Data room (one agent, wait for it)

Launch one general-purpose agent and wait for it to finish:

> You are the data-room agent of the stock-analysis-teardown skill. Read SKILL_DIR/agents/data-room.md and follow it exactly. RUN_DIR=<abs path>. SKILL_DIR=<abs path>. Ticker: <TICKER>. Peers requested by the user: <list or "none">.

When it returns, check that `RUN_DIR/data/fact-pack.md`, `data/metrics.json` and `data/peers.json` exist. If the agent reported a blocking problem (no financial data at all), tell the user and stop.

## 3. Five analysts (in parallel)

Launch all five in one message so they run at the same time. Each gets the same prompt shape:

> You are the <NAME> agent of the stock-analysis-teardown skill. Read SKILL_DIR/agents/_analyst-common.md and SKILL_DIR/agents/<NAME>.md and follow them exactly. RUN_DIR=<abs path>. SKILL_DIR=<abs path>. Ticker: <TICKER>.

`NAME` is `part1-business`, `part1-strategy`, `part2-financials`, `part3-competition`, `part4-valuation`.

Wait until all five have reported. Then confirm each part exists and passes:

```
python3 SKILL_DIR/scripts/validate.py RUN_DIR --part parts/<NAME>.json
```

If a part is missing or fails badly, relaunch that one agent with the failure output in its prompt. Do not fix parts yourself. If an agent fails twice, continue and tell the editor which sections are missing.

## 4. Verifier-editor (one agent, wait)

> You are the verifier-editor agent of the stock-analysis-teardown skill. Read SKILL_DIR/agents/verifier-editor.md and follow it exactly. RUN_DIR=<abs path>. SKILL_DIR=<abs path>. Ticker: <TICKER>.

When it returns, `python3 SKILL_DIR/scripts/validate.py RUN_DIR` must print PASS. If it does not, send the output back to the same agent (SendMessage) or relaunch it.

## 5. Designer (one agent, wait)

> You are the designer agent of the stock-analysis-teardown skill. Read SKILL_DIR/agents/designer.md and follow it exactly. RUN_DIR=<abs path>. SKILL_DIR=<abs path>. Ticker: <TICKER>.

## 6. Check and report

Confirm the PDF exists and the page count matches (`render.mjs` prints both; `build/qa.json` has the details). Look at `RUN_DIR/build/shots/contact-sheet.png` yourself, then open every slide that has a chart (`build/shots/slide-NN.png`) at full size. The contact sheet is too small to catch a wrong chart. For each one, say in one sentence what the chart alone shows, then check it against the title, the bullets and the takeaway: same numbers, same words, same precision, and no claim the chart contradicts. Send any mismatch to the designer or the editor before you report. Each fix is a class of mistake, so check every other chart for the same thing, not just the one you found.

When you hand the PDF over, the person may already have an older copy open. macOS Preview keeps an open PDF in memory and does not reload it. Close any open copy (`osascript -e 'tell application "Preview" to close every document saving no'`) before `open`, and never make extra copies of the PDF under other names.

Tell the user, briefly:

- the PDF path
- page count and how long the run took
- the verdict and verdict line from `deck.json` meta
- data confidence and any sections skipped or gaps the agents reported
- that it is research, not investment advice

Offer to open the PDF (`open <path>` on macOS).

## Notes

- A run takes roughly 30 to 60 minutes and uses a lot of tokens, because five agents research the web in parallel.
- Every number on a slide is either computed by the scripts, cited to a numbered source, or marked as the teardown's own view. `validate.py` enforces this before anything is rendered.
- The scripts use only the Python standard library. The renderer needs Node 22 or newer (one npm dependency, ECharts) and a local Chrome.
