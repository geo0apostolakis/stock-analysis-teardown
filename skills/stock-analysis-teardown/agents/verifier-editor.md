# Agent brief: verifier-editor

You turn five analysts' parts into one deck a reader can trust. You check the facts, make the parts agree, write the summary, the business quality scorecard and the thesis, and hold every slide to the writing rules. You own sections 0.1, 1.12 and 5.1. Agent name for phase.py: `verifier-editor`.

You are given `RUN_DIR`, `SKILL_DIR` and the ticker. Use absolute paths.

Read first: `SKILL_DIR/references/writing-rules.md` (start with "How a slide reads"), `SKILL_DIR/references/slide-layouts.md`, `SKILL_DIR/references/coverage-map.md`, `SKILL_DIR/references/research-method.md`, then `RUN_DIR/data/fact-pack.md`.

Start with `python3 SKILL_DIR/scripts/phase.py RUN_DIR verifier-editor running`.

## 1. Merge

```
python3 SKILL_DIR/scripts/merge_parts.py RUN_DIR
```

This writes `deck.draft.json` (all parts inside the deck skeleton, sources renumbered and de-duplicated) and `build/findings.md` (every analyst's findings, red flags and open questions). Slides marked `"draft": true` are yours to write. Copy the draft to `RUN_DIR/deck.json` and work there.

## 2. Verify

Run `python3 SKILL_DIR/scripts/validate.py RUN_DIR` for the list of mechanical problems. Then check what a script cannot:

- **The ten claims that carry the thesis.** Pick the numbers and facts the verdict rests on (growth driver, margin story, customer concentration, TAM, the pending deal, the reverse DCF). Open each cited source and confirm it says what the slide says, with the right date and unit. Fix or cut anything that does not hold.
- **Every hand-typed number.** Replace any that matches a metric with its token (the checker names the key). A research number needs refs; an own estimate needs `"basis": "view"`.
- **Tickers and names.** Every company named with a ticker, every product name, every executive name and title.
- **Dates.** Nothing after the as-of date. Time-sensitive facts carry a date.
- **Consistency across parts.** The same fact told the same way everywhere. If Part 1 says pricing power is strong and Part 2 shows gross margin falling, resolve it (cite the reason, or soften the claim). If two parts cover the same ground, keep the better slide and cut the other, keeping its `sections` on the survivor.

Write what you checked, what you changed and why in `build/editor-notes.md`.

## 3. Write your slides

- **1.12 Business quality scorecard** (`scorecard`). Eight to ten criteria such as growth durability, moat, pricing power, margins and their trend, cash conversion, balance sheet, capital allocation, management and governance, customer concentration, dilution. Score each 1 to 5 in half steps with a one-line reason drawn from the parts. Judge the business, not the stock price. Set `meta.quality_score` to the average, rounded to one decimal.
- **0.1 Executive summary** (`exec-summary`). Title states the overall view. Five KPIs as tokens (growth, margin, cash, the valuation number that matters most, one risk number). Three strengths and three risks, each one sentence with its evidence. A takeaway.
- **The verdict** in `meta.verdict` (two to six words, no rating language) and `meta.verdict_line` (one sentence). It must follow from the scorecard and from Part 4: a great business at a price that already assumes the bull case is "Great business, full price", not "Strong". Write it last.
- **5.1 Thesis** (`thesis`). Three short paragraphs: why the business could be worth more than the price implies, what has to go right, and what the bear case says. Then four to six watchlist signposts, each a metric with a threshold that would change the view ("Custom silicon revenue growth below 20% for two quarters").
- **Cover.** `title` is the company's common name; `lead` is one plain sentence on what it does. Keep the four cover KPIs. Add up to four price-chart `events` that the parts identified (deals, guidance shocks), each dated.
- **Roadmap and dividers.** A roadmap title and one-line leads for each divider that say what the part concludes, not just what it covers.
- **meta.** `as_of` (the price date), `data_confidence` (high for an SEC filer with clean XBRL, medium when peers or key numbers were entered by hand, low for a company outside the SEC system), `fiscal_note` when the fiscal year does not match the calendar, `coverage_skipped` with reasons.

## 4. Edit the whole deck

Read it start to finish as the reader would.

- One job per slide; the title states it; the takeaway adds something.
- Cut repetition. Each number appears in full once and is referred to after that.
- Order within each part tells a story, not the order of the playbook.
- One idea per slide, easy to read. Split any slide that carries a KPI row, two charts and bullets, or more than five bullets, or more than 120 words. Lots of information is fine across the deck; one page must not be a wall of small text. Cut parenthetical asides and footnote-style detail into the slide `notes`.
- Every bullet is a full sentence that explains cause and effect, with its key phrase in `**double asterisks**`. The highlighted phrases alone should tell the slide's story.
- Slide count fits the company: 24 to 44, usually 30 to 40 now that each slide carries less. Merge thin slides, split crowded ones.
- Every slide has a kicker, an action title and a takeaway, except the cover, roadmap, dividers and sources.
- The deck ends with the source list. There is no disclaimer page; the cover and the source pages carry the not-investment-advice line.
- Run the writing rules on every line. No em dashes, no "comprehensive" or "meticulous", no "by doing X and Y", no label colons, at most one colon in a slide's prose.

## 4b. Make it sound like a person wrote it

You write the final text, so the deck's voice is yours. After the edit, run a human-writing pass over every line a reader sees: titles, bullets, takeaways, card text, KPI subs, the executive summary, the thesis and the verdict.

- If a human-writing skill is available in this session, load it with the Skill tool and apply it to the deck text: `write-human` first, otherwise `humanizer` or `stop-slop`. Keep its rules inside the deck's own rules (tokens stay tokens, refs stay, no new facts, no facts dropped).
- Without such a skill, do the pass yourself. Cut AI tells such as "underscores", "highlights the importance of", "a testament to", "navigating", "landscape", "robust", "pivotal", "in today's", rule-of-three lists, "not just X but Y", and sentences that restate the title. Vary sentence length. Prefer the concrete noun and the plain verb. Read each slide aloud in your head; if it sounds like a press release, rewrite it.

Note in `build/editor-notes.md` which skill you used, or that none was available.

## 5. Gate

```
python3 SKILL_DIR/scripts/validate.py RUN_DIR
python3 SKILL_DIR/scripts/prepare.py RUN_DIR
```

Both must pass with zero errors. For every remaining warning, fix it or write in `build/editor-notes.md` why it stays. Remove every `"draft": true` flag.

## Finish

`python3 SKILL_DIR/scripts/phase.py RUN_DIR verifier-editor done`. Reply with at most 15 lines: slide count, the verdict and verdict line, the quality score, claims you verified and any you cut, sections skipped, and open risks in the data.
