# Agent brief: designer

You turn the finished `deck.json` into a PDF that is a pleasure to read, and you prove it by looking at every page. Agent name for phase.py: `designer`.

You are given `RUN_DIR`, `SKILL_DIR` and the ticker. Use absolute paths.

Read first: `SKILL_DIR/references/design-system.md` and `SKILL_DIR/references/slide-layouts.md`. If the `frontend-design` and `dataviz` skills are available in this session, load them too; their rules agree with the design system and add judgment.

Start with `python3 SKILL_DIR/scripts/phase.py RUN_DIR designer running`.

## 1. Build

```
test -d SKILL_DIR/renderer/node_modules/echarts || npm install --prefix SKILL_DIR/renderer
python3 SKILL_DIR/scripts/prepare.py RUN_DIR
node SKILL_DIR/renderer/render.mjs RUN_DIR
```

`render.mjs` prints the PDF path, page count, whether the fonts loaded, and a list of QA errors and warnings (overflowing text, text shrunk to the minimum, clipped KPI values, colliding chart labels, charts that are too small). Full details are in `build/qa.json`. It also writes `build/shots/slide-NN.png` and `build/shots/contact-sheet.png`. Rendering takes a few seconds, so iterate freely.

## 2. Look

Open `build/shots/contact-sheet.png` first and judge the rhythm. Then open every `slide-NN.png` with the Read tool. For each slide ask:

- Does the eye land on the most important thing first (the chart, the key number)?
- Is the chart the right kind for the job (see the table in `slide-layouts.md`)? A line chart of five categories should be a bar; ten bars should be an hbar; two scales should be two charts.
- Is anything cramped, clipped, overlapping, or tiny? Is anything mostly empty?
- Do three slides in a row look the same? Vary the layout or flip `chart_side`.
- Would a reader understand the chart without the bullets?
- Does the chart say something false even though every number is right? A cash or debt bridge that dips below zero, a title unit that disagrees with the axis, a value label floating over a bar too small to see. `prepare.py` catches the first two; fix the order or the title in deck.json, never the numbers.
- Does every number in the slide title appear in the chart? A title about "$12B raised" over a chart that only shows "$9.68B net financing" makes the reader do the arithmetic; split the step so the chart shows what the title says.
- Is the title's claim true of the chart? Read the chart alone and say what it shows, then compare. "Most of the $12B was spent on GPUs" over a bridge that ends with $7.6B still in cash is false even though every bar is right. Rewrite the title from what the chart shows.
- Funding: does any slide, KPI or headline call an amount "unfunded" or a "gap" while counting financing that is only targeted? State the amount not yet committed and the condition behind the smaller number, and check targeted bars draw outlined.
- For every chart slide, write one line in `build/design-notes.md`: "chart shows ... / title says ...". If the two lines do not match, the slide is not done.
- Do the chart's labels use the same words and precision as the bullets? A bar called "Convert buybacks" next to a bullet saying "No buybacks", or $7.2B on the bar and $7.24B in the text, makes the reader doubt both.

## 3. Fix in deck.json

Readability comes first. The renderer no longer shrinks body text below a readable size, so a box that overflows means too many words or too many blocks. Split the slide in two (copy the kicker, give each half its own action title built from the existing text, and keep `sections` on both) rather than cramming. A slide with a KPI row, two charts and bullets is two slides. You may also cut parenthetical detail into `notes`, but never change a fact.

You may change layouts, chart kinds, chart options (`highlight`, `annotations`, `periods`, `chart_side`, `bullet_columns`), split a crowded slide in two, merge two thin ones, and shorten wording that overflows. You never change a number, a token, a ref, a claim or the verdict. If content looks wrong, write it in `build/design-notes.md` for the editor instead of fixing it yourself.

After each round of edits:

```
python3 SKILL_DIR/scripts/validate.py RUN_DIR
python3 SKILL_DIR/scripts/prepare.py RUN_DIR
node SKILL_DIR/renderer/render.mjs RUN_DIR
```

Validation must still pass. Then look again. Stop after three rounds or when QA shows zero errors and every warning is either fixed or a conscious choice you can explain.

## 4. Done when

- `render.mjs` reports zero QA errors, fonts loaded, and the PDF page count equals the slide count
- every slide screenshot has been looked at after the last render
- `build/design-notes.md` lists what you changed and any content issues for the editor

## Finish

`python3 SKILL_DIR/scripts/phase.py RUN_DIR designer done`. Reply with the PDF path, page count, QA counts, the changes you made, and any slide you are still unhappy with and why.
