#!/usr/bin/env python3
"""The gate before rendering. Checks structure, coverage, references and every number.

usage: validate.py RUN_DIR [--deck FILE]           full deck (default RUN_DIR/deck.json)
       validate.py RUN_DIR --part parts/X.json     one analyst's part: its slides, its sources,
                                                   and the playbook ids that agent owns

Checks
  structure   meta fields, unique slide ids, known layouts and chart kinds, the content each layout
              needs (a chart slide has a chart, a scorecard has 4+ rows, ...), cover first,
              exec summary early, the source list at the end, 24 to 44 slides,
              and one idea per slide (density limits below)
  coverage    every playbook id in schema/coverage.json is on a slide (slide.sections) or listed in
              meta.coverage_skipped with a reason; core ids cannot be skipped
  references  every ref points at a source, every source has a title and url, unused sources
  numbers     runs check_numbers.py (hand-typed numbers, tickers, peers, writing rules)
Exit code 1 on any error. Prints PASS or FAIL last.
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _common import read_json, run_paths, write_json  # noqa: E402
import check_numbers  # noqa: E402

LAYOUT_NEEDS = {
    "cover": [], "roadmap": [], "divider": [], "sources": [], "disclaimer": [],
    "exec-summary": ["strengths", "risks", "kpis"],
    "text": ["bullets|columns|paragraphs"],
    "text-chart": ["charts", "bullets|paragraphs"],
    "chart": ["charts"],
    "two-charts": ["charts"],
    "kpis-chart": ["kpis", "charts"],
    "table": ["table"],
    "text-table": ["table", "bullets|paragraphs"],
    "cards": ["cards"],
    "matrix": ["matrix"],
    "timeline": ["timeline"],
    "scorecard": ["scorecard"],
    "thesis": ["paragraphs", "watchlist"],
}
CHART_KINDS = {"bar", "stacked-bar", "stacked-100", "line", "area", "hbar", "waterfall", "sankey", "scatter",
               "football-field", "maturity-ladder", "price", "segmented-bar"}
NO_TAKEAWAY = {"cover", "roadmap", "divider", "sources", "disclaimer"}
TABLE_FROM = {"peers", "financials", "sensitivity", "scenarios"}



# ---------------------------------------------------------------- density
# One idea per slide, read at a glance: a chart and a few short bullets with the key phrase highlighted.
LIGHT = {"cover", "roadmap", "divider", "sources", "disclaimer"}
DENSE_OK = {"exec-summary", "scorecard", "thesis", "table"}   # their own fixed structure
WORD_KEYS = {"text", "lead", "body", "sub", "takeaway"}
TOKEN_RE = re.compile(r"\{\{[^}]+\}\}")


def _words(x):
    return len(TOKEN_RE.sub("N", x).split()) if isinstance(x, str) else 0


def _slide_words(node, top=True):
    n = 0
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("charts", "table", "notes", "refs", "sources", "id", "matrix"):
                continue
            if k in WORD_KEYS and isinstance(v, str):
                n += _words(v)
            elif k == "paragraphs" and isinstance(v, list):
                n += sum(_words(p) if isinstance(p, str) else _slide_words(p, False) for p in v)
            elif isinstance(v, (dict, list)):
                n += _slide_words(v, False)
    elif isinstance(node, list):
        n += sum(_slide_words(x, False) for x in node)
    return n


def density(sl, sid, lay, err, warn):
    if lay in LIGHT:
        return
    bullets = [b for b in (sl.get("bullets") or []) if isinstance(b, dict)]
    if len(bullets) > 5:
        err(sid, f"{len(bullets)} bullets; one idea per slide takes three to five. Split the slide or cut")
    for i, b in enumerate(bullets):
        w = _words(b.get("lead", "")) + _words(b.get("text", ""))
        if w > 38:
            err(f"{sid}.bullets[{i}]", f"{w} words; a bullet is one or two lines (under 30 words)")
        elif w > 30:
            warn(f"{sid}.bullets[{i}]", f"{w} words; aim for under 30")
    if bullets and not any("**" in (b.get("text", "") + b.get("lead", "")) or b.get("lead") for b in bullets):
        warn(sid, "no highlighted phrase; put the key phrase of each bullet in **double asterisks**")
    for i, c in enumerate(sl.get("cards") or []):
        if _words(c.get("body", "")) > 45:
            warn(f"{sid}.cards[{i}]", "card body over 45 words; cut it to the point")
    if lay in DENSE_OK:
        total = _slide_words(sl)
        if total > 170:
            warn(sid, f"{total} words on the slide; it will read as a wall of text")
        return
    if len(sl.get("kpis") or []) > 3:
        err(sid, f"{len(sl['kpis'])} KPIs; a content slide shows at most three")
    blocks = (1 if sl.get("kpis") else 0) + len(sl.get("charts") or []) + (1 if bullets or sl.get("paragraphs") or sl.get("columns") else 0) \
        + (1 if sl.get("table") else 0) + (1 if sl.get("cards") else 0) + (1 if sl.get("timeline") else 0)
    if blocks > 3:
        err(sid, f"{blocks} blocks (KPI row, charts, text, table, cards); one idea per slide is one chart or table plus text. Split it")
    elif blocks == 3:
        warn(sid, "three blocks on one slide; make sure it still reads at a glance")
    total = _slide_words(sl)
    if total > 150:
        err(sid, f"{total} words of text; keep a slide under 120. Split it or cut")
    elif total > 120:
        warn(sid, f"{total} words of text; aim for under 120")


def coverage_spec():
    return read_json(os.path.join(HERE, "..", "schema", "coverage.json"))["sections"]


def validate(run_dir, deck_path=None, part=None):
    paths = run_paths(run_dir)
    path = part or deck_path or os.path.join(paths["run"], "deck.json")
    deck = read_json(path)
    if deck is None:
        return [("error", "file", f"cannot read {path}")], path
    E = []
    err = lambda w, m: E.append(("error", w, m))  # noqa: E731
    warn = lambda w, m: E.append(("warn", w, m))  # noqa: E731
    slides = deck.get("slides") or []
    sources = deck.get("sources") or []
    meta = deck.get("meta") or {}

    # meta
    if not part:
        for k in ("ticker", "company", "as_of", "verdict", "verdict_line"):
            if not meta.get(k):
                err("meta", f"missing meta.{k}")
        if meta.get("verdict") and not 2 <= len(meta["verdict"].split()) <= 6:
            warn("meta.verdict", "verdict should be two to six words")
        if meta.get("as_of") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", meta["as_of"]):
            err("meta.as_of", "as_of must be YYYY-MM-DD")
        qs = meta.get("quality_score")
        if qs is not None and not (1 <= qs <= 5):
            err("meta.quality_score", "quality_score must be between 1 and 5")

    # sources
    ids = [s.get("id") for s in sources]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        err("sources", f"duplicate source ids {dup}")
    for s in sources:
        if not re.fullmatch(r"S\d+", str(s.get("id", ""))):
            err("sources", f"bad source id {s.get('id')!r}; use S1, S2, ...")
        if not s.get("title") or not s.get("url"):
            err(f"sources.{s.get('id')}", "every source needs a title and a url")
        if s.get("type") in ("industry", "analysis") and "vendor" not in s:
            warn(f"sources.{s.get('id')}", "say whether the publisher sells related products (vendor: true/false)")

    # slides
    sids = [s.get("id") for s in slides]
    dup = sorted({i for i in sids if sids.count(i) > 1})
    if dup:
        err("slides", f"duplicate slide ids {dup}")
    used_refs = set()

    def scan(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "refs" and isinstance(v, list):
                    used_refs.update(v)
                else:
                    scan(v)
        elif isinstance(o, list):
            for x in o:
                scan(x)

    for sl in slides:
        sid = sl.get("id", "?")
        lay = sl.get("layout")
        if lay not in LAYOUT_NEEDS:
            err(sid, f"unknown layout {lay!r}")
            continue
        if not sl.get("title") and lay not in ("cover",):
            err(sid, "missing title")
        for need in LAYOUT_NEEDS[lay]:
            if not any(sl.get(k) for k in need.split("|")):
                err(sid, f"layout {lay} needs {need.replace('|', ' or ')}")
        if sl.get("draft"):
            err(sid, "still marked draft; write it and remove \"draft\": true")
        if lay not in NO_TAKEAWAY and not sl.get("takeaway"):
            warn(sid, "no takeaway (the 'Bottom line' sentence)")
        if lay not in NO_TAKEAWAY and lay != "exec-summary" and not sl.get("kicker"):
            warn(sid, "no kicker (e.g. 'Part 2 · Cash flow')")
        charts = sl.get("charts") or []
        if lay == "chart" and len(charts) != 1:
            err(sid, "layout chart takes exactly one chart")
        if lay == "two-charts" and len(charts) != 2:
            err(sid, "layout two-charts takes exactly two charts")
        if lay == "text-chart" and len(charts) > 2:
            err(sid, "layout text-chart takes one or two charts")
        for i, ch in enumerate(charts):
            k = ch.get("kind")
            if k not in CHART_KINDS:
                err(f"{sid}.charts[{i}]", f"unknown chart kind {k!r}")
            if not ch.get("title"):
                err(f"{sid}.charts[{i}]", "chart needs a short title that names the measure and unit")
            if k in ("bar", "stacked-bar", "stacked-100", "line", "area", "hbar"):
                ser = ch.get("series") or []
                if not ser:
                    err(f"{sid}.charts[{i}]", "chart has no series")
                for s in ser:
                    if not s.get("metric") and not s.get("data"):
                        err(f"{sid}.charts[{i}]", f"series {s.get('name')!r} needs metric or data")
                if len(ser) > 4:
                    warn(f"{sid}.charts[{i}]", f"{len(ser)} series; four is the readable limit")
                if not ch.get("categories") and any(not s.get("metric") for s in ser):
                    err(f"{sid}.charts[{i}]", "hand-typed series need categories")
            if k == "waterfall" and not ch.get("steps"):
                err(f"{sid}.charts[{i}]", "waterfall needs steps")
            if k == "segmented-bar" and not ch.get("parts"):
                err(f"{sid}.charts[{i}]", "segmented-bar needs parts")
            if k == "scatter" and not (ch.get("points") or ch.get("from") == "peers"):
                err(f"{sid}.charts[{i}]", "scatter needs points or from: peers")
        t = sl.get("table")
        if t:
            if t.get("from") and t["from"] not in TABLE_FROM:
                err(f"{sid}.table", f"unknown table source {t['from']!r}")
            if not t.get("from") and not (t.get("columns") and t.get("rows")):
                err(f"{sid}.table", "a hand-made table needs columns and rows")
            if not t.get("from"):
                n = len(t.get("columns") or [])
                for r in t.get("rows") or []:
                    if len(r) != n:
                        err(f"{sid}.table", f"row has {len(r)} cells, header has {n}")
                        break
                if len(t.get("rows") or []) > 14:
                    warn(f"{sid}.table", "more than 14 rows will shrink the text; split the table")
        if lay == "cards" and not 2 <= len(sl.get("cards") or []) <= 6:
            err(sid, "cards takes two to six cards")
        if lay == "scorecard":
            rows = sl.get("scorecard") or []
            if len(rows) < 4:
                err(sid, "scorecard needs at least four criteria")
            for r in rows:
                if not isinstance(r.get("score"), (int, float)) or not 1 <= r["score"] <= 5:
                    err(sid, f"score for {r.get('criterion')!r} must be 1 to 5")
        if lay == "thesis" and len(sl.get("watchlist") or []) < 3:
            err(sid, "thesis needs at least three 'what would change my mind' items")
        if lay == "matrix" and len((sl.get("matrix") or {}).get("points") or []) < 2:
            err(sid, "matrix needs at least two points")
        if lay == "exec-summary":
            if len(sl.get("strengths") or []) < 2 or len(sl.get("risks") or []) < 2:
                err(sid, "exec summary needs at least two strengths and two risks")
            if len(sl.get("kpis") or []) > 6:
                warn(sid, "more than six KPIs will not fit in one row")
        density(sl, sid, lay, err, warn)
        scan(sl)

    src_ids = set(ids)
    bad = sorted(r for r in used_refs if r not in src_ids and r != "view")
    if bad:
        err("refs", f"refs with no matching source: {bad}")
    unused = sorted((set(ids) - used_refs), key=lambda x: int(x[1:]) if x[1:].isdigit() else 0)
    if unused:
        warn("sources", f"{len(unused)} sources are never cited: {unused[:12]}{' ...' if len(unused) > 12 else ''}")

    # order and size (full deck only)
    spec = coverage_spec()
    if not part:
        lays = [s.get("layout") for s in slides]
        if not lays or lays[0] != "cover":
            err("order", "the first slide must be the cover")
        if "exec-summary" not in lays[:4]:
            err("order", "the executive summary must be in the first four slides")
        if not lays or lays[-1] != "sources":
            err("order", "the deck ends with the source list (the cover carries the not-investment-advice line)")
        if "disclaimer" in lays:
            err("order", "no disclaimer page; the cover and the source pages carry the not-investment-advice line")
        if "sources" not in lays:
            err("order", "a sources slide is required")
        n = len(slides)
        if n < 15:
            err("size", f"{n} slides; the minimum is 15 even for a small company")
        elif not 24 <= n <= 44:
            warn("size", f"{n} slides; the usual range is 24 to 44")
        covered = {sec for s in slides for sec in (s.get("sections") or [])}
        skipped = {x.get("id"): x.get("reason") for x in meta.get("coverage_skipped") or []}
        for c in spec:
            if c["id"] in covered:
                continue
            if c["id"] in skipped:
                if c["core"]:
                    err("coverage", f"{c['id']} {c['title']} is core and cannot be skipped")
                elif not (skipped[c['id']] or "").strip():
                    err("coverage", f"{c['id']} skipped without a reason")
                continue
            err("coverage", f"{c['id']} {c['title']} is not on any slide and not in meta.coverage_skipped")
        unknown = covered - {c["id"] for c in spec}
        if unknown:
            warn("coverage", f"unknown section ids on slides: {sorted(unknown)}")
    else:
        agent = (deck.get("agent") or os.path.splitext(os.path.basename(path))[0])
        owned = [c for c in spec if c["owner"] == agent]
        covered = {sec for s in slides for sec in (s.get("sections") or [])}
        skipped = {x.get("id") for x in deck.get("coverage_skipped") or []}
        for c in owned:
            if c["id"] not in covered and c["id"] not in skipped:
                (err if c["core"] else warn)("coverage", f"{c['id']} {c['title']} is not covered by this part")

    # numbers and writing
    issues, _ = check_numbers.check(run_dir, path)
    E += issues
    return E, path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--deck")
    ap.add_argument("--part")
    a = ap.parse_args()
    part = os.path.join(a.run_dir, a.part) if a.part and not os.path.isabs(a.part) and not os.path.exists(a.part) else a.part
    E, path = validate(a.run_dir, a.deck, part)
    errs = [e for e in E if e[0] == "error"]
    warns = [e for e in E if e[0] == "warn"]
    for l, w, m in errs + warns:
        print(f"{l.upper():5} {w}: {m}")
    out = os.path.join(run_paths(a.run_dir)["build"], "validate.json" if not part else f"validate-{os.path.basename(path)}")
    write_json(out, {"file": path, "errors": len(errs), "warnings": len(warns),
                     "issues": [{"level": l, "where": w, "msg": m} for l, w, m in E]})
    print(f"\n{os.path.basename(path)}: {len(errs)} errors, {len(warns)} warnings")
    print("PASS" if not errs else "FAIL")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
