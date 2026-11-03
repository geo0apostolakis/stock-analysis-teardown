# The run folder and its files

One teardown is one folder, `<OUTPUT_ROOT>/<TICKER>-<YYYY-MM-DD>/`. `OUTPUT_ROOT` is `$TEARDOWN_OUTPUT_DIR`, or `./teardowns` when that is not set. Everything an agent needs is in this folder, and everything it produces goes back into it, so any step can be re-run or inspected.

```
MRVL-2026-11-02/
  run.json                  identity, as-of date, phase status (scripts/phase.py shows it)
  data/
    identity.json           SEC CIK, legal and display name, exchange, fiscal year end, filer type
    sec/                    raw SEC JSON (company facts, submissions)
    statements.json         income, cash flow and balance sheet by fiscal year, quarter and TTM, with accession numbers
    market.json             price, five years of daily closes, splits, dividends, beta, returns, 10-year yield
    metrics.json            every computed series and the flat "values" map that tokens read
    extra_metrics.json      numbers agents found in documents, each with a citation
    financials.md           five-year table for reading
    filings/                10-K or 20-F (whole and by Item), 10-Q, proxy, recent 8-K releases, index.json
    insiders.json           Form 4 open-market buys and sells by insider (only Form 4s where this company is the issuer)
    adr.json                for a 20-F filer, shares per ADS read from the 20-F, with the sentence it came from
    peers/<TICKER>/         the same data for each SEC-filing peer
    peers_manual.json       peers that do not file with the SEC, entered by hand with sources
    peers.json              the peer table
    valuation_inputs.json   scenario assumptions, each with a reason (part4-valuation edits it)
    valuation.json          WACC, scenarios, sensitivity grid, reverse DCF, football field
    fact-pack.md            the data-room agent's briefing for the analysts
  notes/<agent>/            research logs with sources
  parts/<agent>.json        each analyst's slides and sources
  deck.draft.json           the parts merged into the deck skeleton (merge_parts.py)
  deck.json                 the finished deck (verifier-editor)
  build/                    findings.md, check and validate reports, deck.resolved.json, deck.html,
                            qa.json, shots/slide-NN.png, shots/contact-sheet.png, design-notes.md
  MRVL-teardown-2026-11-02.pdf
```

## Part file (`parts/<agent>.json`)

```json
{
  "agent": "part2-financials",
  "sources": [
    {"id": "S1", "title": "Form 10-K for fiscal 2026", "publisher": "Marvell Technology via SEC EDGAR",
     "url": "https://www.sec.gov/Archives/edgar/data/1835632/000183563226000011/mrvl-20260131.htm",
     "date": "2026-03-11", "type": "filing"}
  ],
  "slides": [ { "id": "rev-growth", "part": "part2", "sections": ["2.1"], "layout": "text-chart", "...": "..." } ],
  "coverage_skipped": [ {"id": "2.7", "reason": "Working capital is stable and small; covered in one bullet on slide bs"} ],
  "findings": ["The three to six things the editor must know, one sentence each, with tokens or refs"],
  "red_flags": ["Anything that could break the thesis or looks wrong in the data"],
  "open_questions": ["What you could not answer and why"]
}
```

Source ids are local to the part. `merge_parts.py` renumbers them across the deck and merges duplicates by URL. Slide `part` values are `part1` for both Part 1 agents, `part2`, `part3` and `part4`.

## Checking a part

```
python3 SKILL_DIR/scripts/validate.py RUN_DIR --part parts/part2-financials.json
```

It checks the slides, the sources, the numbers and the writing, and that the agent covered the playbook ids it owns. A part is done when it prints PASS.

## Phases

`python3 SKILL_DIR/scripts/phase.py RUN_DIR NAME STATUS` records progress. Each agent marks itself `running` at the start and `done` (or `failed` with a note) at the end. The orchestrator reads the phases to resume an interrupted run.
