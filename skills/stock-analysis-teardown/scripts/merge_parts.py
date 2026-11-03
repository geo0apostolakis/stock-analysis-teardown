#!/usr/bin/env python3
"""Combine the five analysts' parts into one draft deck for the verifier-editor.

usage: merge_parts.py RUN_DIR

Reads parts/part1-business.json, part1-strategy.json, part2-financials.json, part3-competition.json,
part4-valuation.json. Each part looks like
  {"agent": "...", "sources": [{"id": "S1", ...}], "slides": [...],
   "coverage_skipped": [{"id": "2.7", "reason": "..."}],
   "findings": ["..."], "red_flags": ["..."], "open_questions": ["..."]}
with source ids local to the part. This script
  * merges sources across parts (same URL = same source) and renumbers them S1, S2, ... in order of
    first use, rewriting every ref
  * makes slide ids unique
  * wraps the parts in the deck skeleton: cover, roadmap, executive summary, a divider per part,
    the 1.12 scorecard after Part 1, the thesis, the financial summary table, sources (the deck ends there).
    Slides the editor must write are marked "draft": true
  * writes deck.draft.json and build/findings.md (every part's findings, red flags, open questions)
"""
import argparse
import copy
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import read_json, run_paths, write_json, write_text  # noqa: E402

ORDER = ["part1-business", "part1-strategy", "part2-financials", "part3-competition", "part4-valuation"]
DIVIDERS = {
    "part1-business": ("p1", "part1", "Part 1", "The business", "What the company sells, to whom, and what protects it."),
    "part2-financials": ("p2", "part2", "Part 2", "The numbers", "Growth, margins, cash, the balance sheet and returns on capital."),
    "part3-competition": ("p3", "part3", "Part 3", "Competitors and owners", "Who it fights, who owns it, and what insiders do."),
    "part4-valuation": ("p4", "part4", "Part 4", "What the price assumes", "Multiples, a reverse DCF and three scenarios."),
}


def norm_url(u):
    u = (u or "").strip()
    u = re.sub(r"#.*$", "", u)
    u = re.sub(r"^https?://(www\.)?", "", u, flags=re.I)
    return u.rstrip("/").lower()


def rewrite_refs(o, mapping):
    if isinstance(o, dict):
        return {k: ([mapping.get(r, r) for r in v] if k == "refs" and isinstance(v, list) else rewrite_refs(v, mapping))
                for k, v in o.items()}
    if isinstance(o, list):
        return [rewrite_refs(x, mapping) for x in o]
    return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    a = ap.parse_args()
    paths = run_paths(a.run_dir)
    run = read_json(paths["run_json"], {}) or {}
    ident = run.get("identity", {})
    m = read_json(os.path.join(paths["data"], "metrics.json"), {}) or {}
    parts = {}
    for name in ORDER:
        p = read_json(os.path.join(paths["run"], "parts", f"{name}.json"))
        if p is None:
            print(f"WARNING: parts/{name}.json is missing")
            continue
        parts[name] = p

    sources, by_url = [], {}
    seen_ids = set()
    body = {}
    skipped = []
    findings = []
    for name in ORDER:
        p = parts.get(name)
        if not p:
            continue
        mapping = {}
        for s in p.get("sources", []):
            key = norm_url(s.get("url")) or f"{name}:{s.get('id')}"
            if key not in by_url:
                g = dict(s)
                g["id"] = f"S{len(sources) + 1}"
                sources.append(g)
                by_url[key] = g["id"]
            mapping[s["id"]] = by_url[key]
        slides = rewrite_refs(copy.deepcopy(p.get("slides", [])), mapping)
        for sl in slides:
            base = sl.get("id") or "slide"
            sid, n = base, 2
            while sid in seen_ids:
                sid, n = f"{base}-{n}", n + 1
            sl["id"] = sid
            seen_ids.add(sid)
        body[name] = slides
        skipped += p.get("coverage_skipped", [])
        findings.append((name, p.get("findings", []), p.get("red_flags", []), p.get("open_questions", [])))

    company = ident.get("display_name") or ident.get("name") or ident.get("ticker")
    deck = {
        "meta": {"ticker": ident.get("ticker"), "company": company, "exchange": ident.get("exchange"),
                 "as_of": (m.get("meta", {}).get("price_time") or run.get("as_of") or "")[:10],
                 "verdict": "", "verdict_line": "", "quality_score": None, "data_confidence": "",
                 "fiscal_note": "", "coverage_skipped": skipped},
        "sources": sources,
        "slides": [],
    }
    S = deck["slides"]
    S.append({"id": "cover", "part": "cover", "layout": "cover", "title": company, "draft": True,
              "kpis": [{"label": "Share price", "value": "{{m:price|ps}}"}, {"label": "Market cap", "value": "{{m:market_cap|money}}"},
                       {"label": "P/E, trailing", "value": "{{m:pe_ttm|x}}"}, {"label": "EV / sales, trailing", "value": "{{m:ev_sales_ttm|x}}"}],
              "charts": [{"kind": "price", "title": "Share price, five years", "source": "Yahoo Finance"}]})
    S.append({"id": "roadmap", "part": "summary", "layout": "roadmap", "kicker": "Contents", "title": "", "draft": True})
    S.append({"id": "exec", "part": "summary", "layout": "exec-summary", "sections": ["0.1"], "kicker": "Executive summary",
              "title": "", "kpis": [], "strengths": [], "risks": [], "takeaway": "", "draft": True})
    for name in ORDER:
        if name in DIVIDERS:
            did, part, kicker, title, lead = DIVIDERS[name]
            S.append({"id": did, "part": part, "layout": "divider", "kicker": kicker, "title": title, "lead": lead})
        S.extend(body.get(name, []))
        if name == "part1-strategy":
            S.append({"id": "scorecard", "part": "part1", "layout": "scorecard", "sections": ["1.12"],
                      "kicker": "Part 1 · Business quality", "title": "", "scorecard": [], "takeaway": "", "draft": True})
    S.append({"id": "thesis", "part": "thesis", "layout": "thesis", "sections": ["5.1"], "kicker": "Thesis",
              "title": "", "paragraphs": [], "watchlist": [], "takeaway": "", "draft": True})
    S.append({"id": "financials", "part": "appendix", "layout": "table", "kicker": "Appendix · Financial summary",
              "title": "Five years of the numbers behind this teardown", "table": {"from": "financials"}})
    S.append({"id": "sources", "part": "appendix", "layout": "sources", "kicker": "Appendix", "title": "Sources"})
    out = os.path.join(paths["run"], "deck.draft.json")
    write_json(out, deck)

    lines = ["# Findings from the five analysts", ""]
    for name, f, r, q in findings:
        lines += [f"## {name}", ""]
        lines += ["Findings:"] + [f"- {x}" for x in f] + [""]
        if r:
            lines += ["Red flags:"] + [f"- {x}" for x in r] + [""]
        if q:
            lines += ["Open questions:"] + [f"- {x}" for x in q] + [""]
    write_text(os.path.join(paths["build"], "findings.md"), "\n".join(lines))
    merged = sum(len(p.get("sources", [])) for p in parts.values()) - len(sources)
    print(f"draft deck: {len(S)} slides ({sum(1 for s in S if s.get('draft'))} for the editor to write), "
          f"{len(sources)} sources ({merged} duplicates merged) -> {out}")
    print(f"findings: {os.path.join(paths['build'], 'findings.md')}")


if __name__ == "__main__":
    main()
