# Writing rules

The deck is read by someone deciding whether to spend an hour on a stock. Every slide earns its place with one clear claim and the evidence for it. `check_numbers.py` enforces the mechanical rules below; the verifier-editor enforces the rest.

## How a slide reads

Write every slide the way a good hand-made research deck reads. One idea per slide. A title that says it, one chart (or a table, or nothing), and three to five full-sentence bullets in large type, each with its key phrase highlighted. A reader should get the point from the title and the highlighted phrases alone in five seconds, and get the evidence by reading the bullets in thirty.

```json
{"layout": "text-chart", "kicker": "Part 2 · Growth",
 "title": "Revenue grew 84% in four years, but the path was anything but smooth",
 "bullets": [
   {"text": "Revenue rose from {{m:revenue@FY2022|money}} to {{m:revenue@FY2026|money}}, **but growth swung with the chip cycle and the shift to data centers**."},
   {"text": "**FY2024 revenue fell {{m:revenue_growth@FY2024|pct}}** as customers worked through excess inventory and carrier and enterprise demand weakened."},
   {"text": "FY2025 was the bottom, **with {{m:revenue_growth@FY2025|pct}} growth** as inventories normalized."},
   {"text": "**FY2026 jumped {{m:revenue_growth@FY2026|pct}}**, driven by AI spending, custom-chip ramps and optical demand."}],
 "charts": [{"kind": "bar", "title": "Revenue growth, % a year", "series": [{"metric": "revenue_growth"}]}],
 "takeaway": "Growth is real but cyclical, so judge FY2027 by data center demand, not by the trend line."}
```

What makes it read well:

- **One idea.** If the slide needs two charts and a KPI row to make its point, it is two slides. More slides with less on each beat fewer packed slides. Lots of information is fine; lots of information on one page is not.
- **Bullets are sentences that explain cause and effect.** "FY2024 revenue fell 7% as customers worked through excess inventory", not "FY2024: −7% (inventory)". Each bullet adds one fact and why it matters.
- **Highlight the key phrase.** Put the part that carries the point in `**double asterisks**`. It prints bold in the accent colour. One highlight per bullet, a phrase not the whole sentence. The highlighted phrases alone should tell the story.
- **Short.** Three to five bullets. One or two lines each (under 30 words). A slide holds under 120 words of text, takeaway included. The validator fails a slide with more than five bullets, more than three KPIs, more than three blocks (KPI row, chart, chart, text, table, cards) or more than 150 words.
- **No clutter.** No footnotes in the body, no parenthetical asides, no "(see S12)". Source numbers go in `refs` and print in the slide footer, not in the text.
- **Big enough to read.** The renderer no longer shrinks text to fit. If text overflows, cut words or split the slide.

## Slide anatomy

- **Kicker.** Where the reader is. `Part 2 · Cash flow`. Short, no sentence.
- **Title.** An action title, one full sentence that states the takeaway. "Free cash flow doubled while net income swung", not "Cash flow analysis". Under 90 characters, no full stop at the end, no question.
- **Lead (optional).** One sentence that frames the evidence below. Most slides do not need one.
- **Body.** One chart, table or set of cards, plus three to five bullets.
- **Takeaway.** The "Bottom line" sentence printed at the bottom. What the reader should conclude, in plain words. It should say something the title did not.

## Bullets

- Start with the point, then the evidence, then why it matters.
- Highlight the key phrase with `**...**` rather than a label. The `lead` field (a bold lead-in ending with a full stop, `"lead": "Switching costs."`) is for lists of named items such as risks or watchlist signposts. Never write "Switching costs: ...".
- One idea per bullet, under 30 words.
- Sub-bullets only when a list genuinely nests.

## Numbers

- Every number that comes from the data is a token: `{{m:revenue@FY2026|money}}`. Never retype a number that exists in `metrics.json`. Tokens cannot drift and cannot be mistyped.
- A number from research carries `refs` on the same bullet, KPI, card or chart.
- A number that is the teardown's own estimate or threshold carries `"basis": "view"`, and the sentence says so ("we would worry below 45%").
- Round for reading. `$8.2B` in prose, `8,195` in a table, `42.1%` when the decimal matters, `42%` when it does not.
- Say the period every time a number could be read two ways. "FY2026", "TTM", "Q2 FY2027", "as of 2 Nov 2026".
- Growth is a change, a margin is a share. "Gross margin rose 4.2 pp to 51.0%", not "rose 4.2%".
- Negative numbers use a real minus sign (the formatter does this). "Net cash" is clearer than "negative net debt".

## Voice

- Write like a person explaining the company to a smart friend, not like a report generator. Plain English. Short sentences. Active verbs. Define an acronym the first time unless it is standard finance (EPS, FCF, ROIC, EBITDA, TTM).
- Skeptical and fair. Give the strongest version of the bull and the bear case. Name what you do not know.
- Separate fact from view. Facts are cited. Views are marked as the teardown's view ("Our read is...", `"basis": "view"`).
- Company claims are claims. "Management targets 60% data center mix", not "Data center will be 60% of revenue".
- No hype, no filler, no throat-clearing ("It is important to note that").

## Banned outright (the checker fails the deck)

- Em dashes (—). Use a full stop, a comma or parentheses. Spaced en dashes used as dashes ( – ) are banned too. An en dash in a range (2022–2026) is fine.
- The words "comprehensive" and "meticulous". Say the specific thing instead, such as how many items were checked or what was covered.
- The "by doing X and Y" construction ("margins rose by cutting costs and raising prices"). Say what happened as its own sentence ("Margins rose. The company cut costs and raised prices.").
- Label colons ("The risk: customers leave."). Use the bullet `lead` field or two sentences. More than one colon in the prose of a slide is flagged. Most slides need none.
- Rating language in the verdict. No Buy, Sell, Hold, Outperform, Overweight or price targets. The verdict is two to six words that describe the view ("Constructive but conditional", "Quality at a full price", "Cheap for a reason").

## Flagged for a second look

AI-sounding phrases ("delve", "tapestry", "testament to", "game-changer", "unparalleled", "it's worth noting", "in today's"), doubled words, exclamation marks, titles over 95 characters, bullets over 240 characters.

## The verdict

The cover and executive summary carry the verdict and one sentence that justifies it. The verdict answers "is this a good business at this price?" in words. It must follow from Part 4 (what the price assumes) and 1.12 (business quality). If they pull in different directions, say that ("Great business, demanding price"). Every page that states a view has "Not investment advice" on the cover and the last page.
