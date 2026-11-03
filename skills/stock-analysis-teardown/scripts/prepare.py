#!/usr/bin/env python3
"""Resolve deck.json into build/deck.resolved.json for the renderer.

usage: prepare.py RUN_DIR [--deck PATH] [--lenient] [--out PATH]

  * text tokens {{m:KEY|FMT}} -> formatted text from metrics.json (one formatter for everything)
  * numeric fields that are a bare token "{{m:KEY}}" -> the raw number
  * chart series with "metric" -> values for the chosen periods
  * "from" shortcuts -> data: income_statement (sankey), valuation (football field, scenarios),
    debt_maturities, market (price chart), peers (scatter, tables), financials and sensitivity tables
  * page numbers, roadmap entries and the sources list
A missing token or metric is an error: the renderer must never print a guess.
"""
import argparse
import copy
import datetime as dt
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import currency_symbol, read_json, run_paths, write_json  # noqa: E402
from numfmt import fmt, parse_token  # noqa: E402

TOKEN = re.compile(r"\{\{\s*m:([^}]+?)\s*\}\}")
FULL_TOKEN = re.compile(r"^\s*\{\{\s*m:([^}]+?)\s*\}\}\s*$")
# financial table cells: plain numbers, the header carries the unit
TABLE_SPEC = {"money_m": "num", "ps": "num2", "days": "num", "x": "x", "pct": "pct1", "shares_m": "num", "ratio": "num2"}


class Ctx:
    def __init__(self, run_dir):
        self.paths = run_paths(run_dir)
        d = self.paths["data"]
        self.m = read_json(os.path.join(d, "metrics.json")) or {"values": {}, "series": {}, "meta": {}}
        self.val = read_json(os.path.join(d, "valuation.json")) or {}
        self.peers = read_json(os.path.join(d, "peers.json")) or {}
        self.market = read_json(os.path.join(d, "market.json")) or {}
        self.meta = self.m.get("meta", {})
        self.sym = self.meta.get("currency_symbol", "$")
        self.errors, self.warnings = [], []

    def sym_for(self, v):
        return currency_symbol(v.get("ccy")) if v.get("ccy") else self.sym

    def text(self, s, where):
        if not isinstance(s, str):
            return s

        def rep(mt):
            key, spec = parse_token(mt.group(1))
            v = self.m["values"].get(key)
            if v is None:
                self.errors.append(f"{where}: unknown metric '{key}'")
                return f"[[missing {key}]]"
            try:
                return fmt(v["v"], v["unit"], spec, sym=self.sym_for(v))
            except ValueError as e:
                self.errors.append(f"{where}: {e}")
                return f"[[bad format {spec}]]"
        return TOKEN.sub(rep, s)

    def number(self, x, where):
        if isinstance(x, (int, float)) or x is None:
            return x
        if isinstance(x, str):
            mt = FULL_TOKEN.match(x)
            if mt:
                key, _ = parse_token(mt.group(1))
                v = self.m["values"].get(key)
                if v is None:
                    self.errors.append(f"{where}: unknown metric '{key}'")
                    return None
                return v["v"]
            try:
                return float(x.replace(",", ""))
            except ValueError:
                self.errors.append(f"{where}: not a number: {x!r}")
        return None


def walk_text(obj, ctx, where):
    """Resolve tokens in every string of a slide except chart/table numeric payloads (handled separately)."""
    if isinstance(obj, str):
        return ctx.text(obj, where)
    if isinstance(obj, list):
        return [walk_text(x, ctx, f"{where}[{i}]") for i, x in enumerate(obj)]
    if isinstance(obj, dict):
        return {k: (v if k in ("charts", "table", "matrix", "refs", "id", "layout", "part", "sections", "notes")
                    else walk_text(v, ctx, f"{where}.{k}")) for k, v in obj.items()}
    return obj


def periods_for(chart, ctx):
    p = chart.get("periods", "display")
    if chart.get("categories"):
        return chart["categories"]
    if p == "all":
        return ctx.meta.get("periods", [])
    if p == "quarterly":
        return ctx.m.get("quarter_periods", [])
    if isinstance(p, list):
        return p
    return ctx.meta.get("display_periods", [])


def series_values(metric, cats, ctx, quarterly, where):
    if quarterly:
        q = ctx.m.get("quarterly", {}).get(metric)
        if q is None:
            ctx.errors.append(f"{where}: no quarterly series '{metric}' (available: {sorted(ctx.m.get('quarterly', {}))})")
            return [None] * len(cats)
        return [q.get(c) for c in cats]
    s = ctx.m.get("series", {}).get(metric)
    if s is None:
        ctx.errors.append(f"{where}: unknown series '{metric}'")
        return [None] * len(cats)
    return [s["values"].get(c) for c in cats]


def resolve_chart(ch, ctx, where):
    ch = copy.deepcopy(ch)
    kind = ch["kind"]
    ch["title"] = ctx.text(ch.get("title", ""), where)
    for k in ("subtitle", "source", "x_label", "y_label"):
        if k in ch:
            ch[k] = ctx.text(ch[k], where)
    ch["sym"] = ctx.sym
    if kind == "sankey" or ch.get("from") == "income_statement":
        return sankey(ch, ctx, where)
    if kind == "football-field":
        return football(ch, ctx, where)
    if kind == "maturity-ladder":
        dm = ctx.meta.get("debt_maturities") or {}
        order = [("maturity_y1", "Year 1"), ("maturity_y2", "Year 2"), ("maturity_y3", "Year 3"),
                 ("maturity_y4", "Year 4"), ("maturity_y5", "Year 5"), ("maturity_after5", "After 5")]
        cats = [lbl for k, lbl in order if k in dm]
        if not ch.get("series"):
            if not cats:
                ctx.errors.append(f"{where}: no debt maturity data in metrics; give categories and series data")
            ch["categories"] = cats
            ch["series"] = [{"name": "Principal due", "data": [dm[k] for k, _ in order if k in dm], "role": "primary"}]
        else:
            # an agent's own buckets: resolve tokens like any other chart
            ch["series"] = [dict(s, name=ctx.text(s.get("name", ""), where),
                                 data=[ctx.number(x, f"{where}.series[{i}]") for x in s.get("data", [])])
                            for i, s in enumerate(ch["series"])]
            ch["categories"] = [ctx.text(c, where) for c in ch.get("categories", [])]
            if any(len(s["data"]) != len(ch["categories"]) for s in ch["series"]):
                ctx.errors.append(f"{where}: series length does not match categories")
        ch["unit"] = ch.get("unit", "money_m")
        ch.setdefault("subtitle", f"Scheduled principal as of {ctx.meta.get('debt_maturities_as_of')}")
    elif kind == "price":
        hist = ctx.market.get("history") or []
        weekly, seen = [], set()
        for r in hist:
            d = dt.date.fromisoformat(r["date"])
            wk = d.isocalendar()[:2]
            if wk in seen:
                weekly[-1] = r
            else:
                weekly.append(r)
                seen.add(wk)
        ch["dates"] = [r["date"] for r in weekly]
        ch["series"] = [{"name": ctx.meta.get("ticker") or "Share price", "data": [r["close"] for r in weekly], "role": "primary"}]
        if ch.get("benchmark"):
            bh = {r["date"]: r["adj"] for r in ctx.market.get("benchmark_history") or []}
            base_s = weekly[0]["adj"] if weekly else None
            bdates = [d for d in ch["dates"] if d in bh]
            if bdates and base_s:
                b0 = bh[bdates[0]]
                ch["series"] = [
                    {"name": ctx.meta.get("ticker"), "data": [r["adj"] / base_s * 100 for r in weekly], "role": "primary"},
                    {"name": "S&P 500 (SPY)", "data": [bh.get(d, None) / b0 * 100 if d in bh else None for d in ch["dates"]], "role": "muted"}]
                ch["unit"] = "num"
                ch.setdefault("subtitle", "Total return, indexed to 100")
        ch.setdefault("unit", "ps")
        ch["sym"] = currency_symbol(ctx.market.get("currency"))
        ch["events"] = [dict(e, label=ctx.text(e.get("label", ""), where)) for e in ch.get("events", [])]
    elif kind == "scatter":
        pts = ch.get("points")
        if not pts and ch.get("from") == "peers":
            xk, yk = ch.get("x_metric", "revenue_growth"), ch.get("y_metric", "ev_sales_ttm")
            pts = []
            for r in ctx.peers.get("rows", []):
                if isinstance(r.get(xk), (int, float)) and isinstance(r.get(yk), (int, float)):
                    pts.append({"label": r["ticker"], "x": r[xk], "y": r[yk], "highlight": bool(r.get("is_subject"))})
            units = {c["key"]: c["unit"] for c in ctx.peers.get("columns", [])}
            ch.setdefault("x_unit", units.get(xk, "num"))
            ch.setdefault("unit", units.get(yk, "num"))
        ch["points"] = [dict(p, x=ctx.number(p.get("x"), where), y=ctx.number(p.get("y"), where),
                             label=ctx.text(p.get("label", ""), where)) for p in (pts or [])]
    elif kind == "waterfall":
        steps = []
        for s in ch.get("steps", []):
            steps.append({"label": ctx.text(s["label"], where), "value": ctx.number(s.get("value"), where),
                          "total": bool(s.get("total"))})
        ch["steps"] = steps
    elif kind == "segmented-bar":
        ch["parts"] = [dict(p, value=ctx.number(p.get("value"), where), label=ctx.text(p.get("label", ""), where))
                       for p in ch.get("parts", [])]
    else:
        cats = periods_for(ch, ctx)
        quarterly = ch.get("periods") == "quarterly"
        out = []
        for i, s in enumerate(ch.get("series", [])):
            s = dict(s)
            s["name"] = ctx.text(s.get("name", ""), where)
            if s.get("metric"):
                s["data"] = series_values(s["metric"], cats, ctx, quarterly, f"{where}.series[{i}]")
                if not ch.get("unit"):
                    ch["unit"] = (ctx.m.get("series", {}).get(s["metric"]) or {}).get("unit", "num") if not quarterly else "money_m"
            else:
                s["data"] = [ctx.number(x, f"{where}.series[{i}]") for x in s.get("data", [])]
            out.append(s)
        ch["series"] = out
        ch["categories"] = [ctx.text(c, where) for c in cats] if cats else ch.get("categories", [])
        if ch.get("series") and ch["categories"] and any(len(s["data"]) != len(ch["categories"]) for s in out):
            ctx.errors.append(f"{where}: series length does not match categories")
        for a in ch.get("annotations", []):
            a["text"] = ctx.text(a.get("text", ""), where)
    ch.setdefault("unit", "num")
    return ch


def sankey(ch, ctx, where):
    p = ch.get("period") or ctx.meta.get("display_periods", [None])[-1]
    S = lambda k: (ctx.m.get("series", {}).get(k) or {}).get("values", {}).get(p)  # noqa: E731
    rev, cogs, gp, rnd, sga, op = S("revenue"), S("cost_of_revenue"), S("gross_profit"), S("rnd"), S("sga"), S("operating_income")
    if None in (rev, gp):
        ctx.errors.append(f"{where}: sankey needs revenue and gross profit for {p}")
        return ch
    links = [{"source": "Revenue", "target": "Cost of revenue", "value": max(rev - gp, 0)},
             {"source": "Revenue", "target": "Gross profit", "value": gp}]
    other = gp - (op or 0) - (rnd or 0) - (sga or 0)
    if rnd:
        links.append({"source": "Gross profit", "target": "R&D", "value": rnd})
    if sga:
        links.append({"source": "Gross profit", "target": "SG&A", "value": sga})
    if other > 0.5:
        links.append({"source": "Gross profit", "target": "Other operating costs", "value": other})
    if op and op > 0:
        links.append({"source": "Gross profit", "target": "Operating income", "value": op})
    nodes = []
    for l in links:
        for n in (l["source"], l["target"]):
            if n not in nodes:
                nodes.append(n)
    ch["nodes"] = [{"name": n} for n in nodes]
    ch["links"] = links
    ch["unit"] = "money_m"
    ch["kind"] = "sankey"
    ch.setdefault("subtitle", f"{p}, {ctx.meta.get('currency')} millions")
    return ch


def football(ch, ctx, where):
    bars = ch.get("bars") or ctx.val.get("football_field") or []
    if not bars:
        ctx.errors.append(f"{where}: no football field data; run valuation.py run")
    ch["bars"] = [{"label": ctx.text(b["label"], where), "low": ctx.number(b.get("low"), where),
                   "high": ctx.number(b.get("high"), where), "mid": ctx.number(b.get("mid"), where),
                   "kind": b.get("kind")} for b in bars]
    ch["price"] = ctx.val.get("price") or (ctx.m["values"].get("price") or {}).get("v")
    ch["unit"] = "ps"
    ch["sym"] = currency_symbol(ctx.meta.get("price_currency") or ctx.meta.get("currency"))
    return ch


def resolve_table(t, ctx, where):
    t = copy.deepcopy(t)
    src = t.get("from")
    if src == "peers":
        cols_all = {c["key"]: c for c in ctx.peers.get("columns", [])}
        cols = t.get("columns") or ["revenue_growth", "gross_margin", "operating_margin", "roic", "pe_ttm", "ev_sales_ttm"]
        header = ["Company"] + [cols_all.get(c, {"label": c})["label"].split(",")[0] for c in cols]
        rows, heat = [], []
        for r in ctx.peers.get("rows", []):
            cells = [f"{r.get('name') or r['ticker']} ({r['ticker']})"]
            hv = [None]
            for c in cols:
                v = r.get(c)
                unit = cols_all.get(c, {}).get("unit", "num")
                sym = "$" if c == "market_cap_usd" else currency_symbol(r.get("currency"))
                cells.append(fmt(v, unit, sym=sym) if isinstance(v, (int, float)) else "n/a")
                hv.append(v if isinstance(v, (int, float)) else None)
            rows.append(cells)
            heat.append(hv)
        t.update({"header": header, "rows": rows, "heat_values": heat, "highlight_row": 0,
                  "col_align": ["left"] + ["right"] * len(cols)})
        manual = [r["ticker"] for r in ctx.peers.get("rows", []) if r.get("manual")]
        t.setdefault("note", "TTM = trailing twelve months. SEC filers computed from filings by metrics.py"
                     + (f"; {', '.join(manual)} entered from cited sources." if manual else "."))
    elif src == "financials":
        cats = ctx.meta.get("display_periods", [])
        keys = t.get("metrics") or ["revenue", "revenue_growth", "gross_margin", "operating_margin", "net_income", "eps_diluted",
                                    "cfo", "fcf", "fcf_margin", "sbc_pct_revenue", "net_debt", "roic"]
        header = [f"{ctx.meta.get('currency')} millions"] + cats
        rows = []
        for k in keys:
            s = ctx.m.get("series", {}).get(k)
            if not s:
                ctx.errors.append(f"{where}: unknown series '{k}'")
                continue
            spec = TABLE_SPEC.get(s["unit"])
            rows.append([s["label"]] + [fmt(s["values"].get(c), s["unit"], spec, sym="")
                                        if s["values"].get(c) is not None else "n/a" for c in cats])
        t.update({"header": header, "rows": rows, "col_align": ["left"] + ["right"] * len(cats)})
    elif src == "sensitivity":
        sens = ctx.val.get("sensitivity")
        if not sens:
            ctx.errors.append(f"{where}: no sensitivity grid; run valuation.py run")
            return t
        psym = currency_symbol(ctx.meta.get("price_currency") or ctx.meta.get("currency"))
        header = ["WACC \\ terminal growth"] + [fmt(g, "pct", "pct1") for g in sens["terminal_growth"]]
        rows, heat = [], []
        for w, row in zip(sens["wacc"], sens["per_share"]):
            rows.append([fmt(w, "pct", "pct1")] + [fmt(x, "ps", "ps0", sym=psym) if x else "n/a" for x in row])
            heat.append([None] + row)
        t.update({"header": header, "rows": rows, "heat_values": heat, "col_align": ["left"] + ["right"] * len(sens["terminal_growth"]),
                  "center_cell": [2, 3]})
        t.setdefault("note", f"Base-case value per share. Current price {fmt(ctx.val.get('price'), 'ps', sym=psym)}.")
    elif src == "scenarios":
        sc = ctx.val.get("scenarios") or {}
        psym = currency_symbol(ctx.meta.get("price_currency") or ctx.meta.get("currency"))
        header = ["Case", "Probability", "10-yr revenue CAGR", "Year-10 owner FCF margin", "Value per share", "vs price"]
        rows = []
        for n in ("bear", "base", "bull"):
            s = sc.get(n)
            if not s:
                continue
            rows.append([n.capitalize(), fmt(s.get("probability"), "pct", "pct"), fmt(s["revenue_cagr_10y"], "pct", "pct1"),
                         fmt(s["year10_fcf_margin"], "pct", "pct1"), fmt(s["per_share"], "ps", sym=psym),
                         fmt(s["upside"], "pct", "pct+")])
        t.update({"header": header, "rows": rows, "col_align": ["left"] + ["right"] * 5})
    else:
        header = [ctx.text(h, where) for h in t.get("columns", [])]
        rows = [[ctx.text(c, where) if isinstance(c, str) else (fmt(c, "num") if isinstance(c, (int, float)) else "")
                 for c in row] for row in t.get("rows", [])]
        t.update({"header": header, "rows": rows})
        t.setdefault("col_align", ["left"] + ["right"] * (len(header) - 1))
    if "note" in t:
        t["note"] = ctx.text(t["note"], where)
    return t


def prepare(run_dir, deck_path=None, strict=True, out_path=None):
    ctx = Ctx(run_dir)
    deck = read_json(deck_path or os.path.join(ctx.paths["run"], "deck.json"))
    if not deck:
        sys.exit("no deck.json")
    out = {"meta": walk_text(deck.get("meta", {}), ctx, "meta"), "sources": deck.get("sources", []), "slides": []}
    out["meta"]["currency_symbol"] = ctx.sym
    out["meta"]["fiscal_period_ends"] = ctx.meta.get("fiscal_period_ends")
    src_ids = {s["id"] for s in out["sources"]}
    for i, sl in enumerate(deck.get("slides", [])):
        where = f"slide {sl.get('id', i)}"
        r = walk_text(sl, ctx, where)
        r["page"] = i + 1
        if "charts" in sl:
            r["charts"] = [resolve_chart(c, ctx, f"{where}.charts[{j}]") for j, c in enumerate(sl["charts"])]
        if "table" in sl:
            r["table"] = resolve_table(sl["table"], ctx, f"{where}.table")
        if "matrix" in sl:
            mx = copy.deepcopy(sl["matrix"])
            for p in mx.get("points", []):
                p["label"] = ctx.text(p.get("label", ""), where)
                p["note"] = ctx.text(p.get("note", ""), where)
            for k in ("x_label", "y_label"):
                if k in mx:
                    mx[k] = ctx.text(mx[k], where)
            r["matrix"] = mx
        # collect refs used on the slide for the footer
        used = set()

        def scan(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k == "refs" and isinstance(v, list):
                        used.update(v)
                    else:
                        scan(v)
            elif isinstance(o, list):
                for x in o:
                    scan(x)
        scan(sl)
        bad = sorted(x for x in used if x not in src_ids)
        if bad:
            ctx.errors.append(f"{where}: refs not in sources: {bad}")
        r["refs_used"] = sorted(used, key=lambda s: int(s[1:]) if s[1:].isdigit() else 0)
        out["slides"].append(r)
    # roadmap: list the dividers with their page numbers
    dividers = [{"label": s["title"], "kicker": s.get("kicker", ""), "page": s["page"]} for s in out["slides"] if s["layout"] == "divider"]
    for s in out["slides"]:
        if s["layout"] == "roadmap" and not s.get("items"):
            s["items"] = dividers
    out["total_pages"] = len(out["slides"])
    out["errors"], out["warnings"] = ctx.errors, ctx.warnings
    out_path = out_path or os.path.join(ctx.paths["build"], "deck.resolved.json")
    write_json(out_path, out)
    for e in ctx.errors:
        print("ERROR:", e, file=sys.stderr)
    print(f"prepared {len(out['slides'])} slides, {len(ctx.errors)} errors -> {out_path}")
    if strict and ctx.errors:
        sys.exit(1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--deck")
    ap.add_argument("--lenient", action="store_true", help="write output even with errors (for drafts)")
    ap.add_argument("--out", help="where to write the resolved deck (default build/deck.resolved.json)")
    a = ap.parse_args()
    prepare(a.run_dir, a.deck, strict=not a.lenient, out_path=a.out)


if __name__ == "__main__":
    main()
