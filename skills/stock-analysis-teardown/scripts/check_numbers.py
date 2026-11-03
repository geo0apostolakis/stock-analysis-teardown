#!/usr/bin/env python3
"""Check every number, ticker and sentence in a deck (or one analyst's part) before it ships.

usage: check_numbers.py RUN_DIR [--deck FILE] [--json OUT]

What it flags
  numbers   A number typed by hand (not a {{m:...}} token) must carry a source ref on the same
            bullet, KPI, card or chart, or on the slide. A hand-typed number that matches a computed
            metric is flagged too: replace it with the token so it cannot drift. Hand-typed chart
            data and literal tables need refs.
  tickers   "Name (TICKER)" pairs are checked against the SEC ticker list and peers.json, so a
            ticker attached to the wrong company is caught (swapped peer tickers are a common deck error).
  peers     Identical values across different peers (a copy-paste sign), margins outside -100%..100%,
            manual peer rows without a source.
  writing   Em dashes, spaced en dashes, banned words, label colons and too many colons, the
            "by doing X and Y" construction, doubled words, exclamation marks, Buy/Sell/Hold
            language in the verdict, overlong titles and bullets.

Exit code 1 when there are errors. Errors must be fixed. Warnings need a look and a reason to keep.
"""
import argparse
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import read_json, run_paths, write_json  # noqa: E402

TOKEN = re.compile(r"\{\{\s*m:[^}]+\}\}")
URL = re.compile(r"https?://\S+")
DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b")
PERIOD = re.compile(r"\b(?:[1-4]Q|Q[1-4]|[12]H|H[12]|FY|CY)\s?'?\d{2,4}\b|\bFY\b|\b(?:Q[1-4]|[12]H)\b")
TICKER_SUFFIX = re.compile(r"\b[\w]+\.(?:TW|TWO|T|HK|KS|KQ|SS|SZ|L|PA|AS|DE|SW|MI|MC|TO|AX|NS|BO|SA|ST|HE|CO|OL)\b")
SECTION_ID = re.compile(r"\b\d{1,2}\.\d{1,2}\b(?=\s*[A-Z(·])")
NUM = re.compile(
    r"(?<![\w.,])(?P<neg>[-\u2212])?(?P<cur>US\$|NT\$|HK\$|A\$|C\$|[$€£¥₩])?\s?"
    r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?:\s?(?P<unit>%|pp\b|bps\b|x\b|×|bn\b|billion\b|million\b|mn\b|trillion\b|B\b|M\b|T\b|K\b))?"
    r"(?![\w%])")

BANNED_ERR = ["comprehensive", "meticulous", "meticulously"]
BANNED_WARN = ["delve", "tapestry", "testament to", "game-changer", "game-changing", "unparalleled",
               "it's worth noting", "it is worth noting", "in today's", "navigate the", "a myriad"]
VERDICT_WORDS = re.compile(r"\b(strong buy|buy|sell|hold|outperform|underperform|overweight|underweight|"
                           r"accumulate|reduce|price target)\b", re.I)
LABEL_COLON = re.compile(r"^\s*[A-Z][\w &/'’()+-]{0,32}:\s")
BY_ING = re.compile(r"\bby\s+\w+ing\b[^.;!?]{0,90}?\band\s+\w+ing\b", re.I)
DOUBLE = re.compile(r"\b(\w{2,})\s+\1\b", re.I)


# ---------------------------------------------------------------- text extraction
def own_refs(obj):
    """refs of an element; basis 'view' (the teardown's own threshold or judgment) counts as a source."""
    refs = list(obj.get("refs") or [])
    if obj.get("basis") == "view":
        refs.append("view")
    return refs


def bullet_parts(b, default_refs=()):
    if isinstance(b, str):
        return [("text", b)], list(default_refs)
    out = []
    for k in ("lead", "text"):
        if b.get(k):
            out.append((k, b[k]))
    for s in b.get("sub", []) or []:
        out.append(("sub", s))
    return out, own_refs(b) or list(default_refs)


def slide_elements(sl):
    """Yield (field, text, refs, kind) for every piece of prose on a slide. kind: prose|label|value|title."""
    slide_refs = list(sl.get("refs") or [])
    for k in ("title", "lead", "takeaway"):
        if sl.get(k):
            yield k, sl[k], slide_refs, "title" if k == "title" else "prose"
    if sl.get("kicker"):
        yield "kicker", sl["kicker"], slide_refs, "label"
    for key in ("bullets", "strengths", "risks", "paragraphs", "watchlist"):
        for i, b in enumerate(sl.get(key) or []):
            parts, refs = bullet_parts(b, ["view"] if key == "watchlist" else [])
            for sub, t in parts:
                yield f"{key}[{i}].{sub}", t, refs, "prose"
    for ci, col in enumerate(sl.get("columns") or []):
        if col.get("heading"):
            yield f"columns[{ci}].heading", col["heading"], [], "label"
        for i, b in enumerate(col.get("bullets") or []):
            parts, refs = bullet_parts(b)
            for sub, t in parts:
                yield f"columns[{ci}].bullets[{i}].{sub}", t, refs, "prose"
    for i, k in enumerate(sl.get("kpis") or []):
        refs = own_refs(k)
        yield f"kpis[{i}].label", k.get("label", ""), refs, "label"
        yield f"kpis[{i}].value", k.get("value", ""), refs, "value"
        if k.get("sub"):
            yield f"kpis[{i}].sub", k["sub"], refs, "prose"
    for i, c in enumerate(sl.get("cards") or []):
        refs = own_refs(c)
        for k in ("tag", "title"):
            if c.get(k):
                yield f"cards[{i}].{k}", c[k], refs, "label"
        if c.get("body"):
            yield f"cards[{i}].body", c["body"], refs, "prose"
        for j, f in enumerate(c.get("facts") or []):
            yield f"cards[{i}].facts[{j}]", f, refs, "prose"
    for i, t in enumerate(sl.get("timeline") or []):
        refs = own_refs(t)
        yield f"timeline[{i}].title", t.get("title", ""), refs, "label"
        if t.get("body"):
            yield f"timeline[{i}].body", t["body"], refs, "prose"
    for i, r in enumerate(sl.get("scorecard") or []):
        yield f"scorecard[{i}].comment", r.get("comment", ""), own_refs(r), "prose"
    mx = sl.get("matrix") or {}
    for i, p in enumerate(mx.get("points") or []):
        if p.get("note"):
            yield f"matrix.points[{i}].note", p["note"], [], "prose"
    for i, ch in enumerate(sl.get("charts") or []):
        refs = (ch.get("refs") or []) + ([ch["source"]] if ch.get("source") else [])
        for k in ("title", "subtitle"):
            if ch.get(k):
                yield f"charts[{i}].{k}", ch[k], refs, "label"
        for j, a in enumerate(ch.get("annotations") or []):
            yield f"charts[{i}].annotations[{j}]", a.get("text", ""), refs, "prose"
        for j, e in enumerate(ch.get("events") or []):
            yield f"charts[{i}].events[{j}]", e.get("label", ""), refs, "prose"
    t = sl.get("table") or {}
    if t.get("note"):
        yield "table.note", t["note"], t.get("refs") or [], "prose"


# ---------------------------------------------------------------- numbers
def clean_for_numbers(text):
    t = TOKEN.sub(" ", text)
    t = URL.sub(" ", t)
    t = DATE.sub(" ", t)
    t = TICKER_SUFFIX.sub(" ", t)
    t = PERIOD.sub(" ", t)
    t = SECTION_ID.sub(" ", t)
    t = re.sub(r"\b\d+(?:\.\d+)?(?=[A-Za-z])", " ", t)   # 800G, 3nm, 1.6T, 5G, 10-K stays below
    t = re.sub(r"\b(?:10|20|40)-[KQF]\b|\b8-K\b|\bForm \d\b|\b13[FDG]\b|\bDEF 14A\b", " ", t)
    return t


def literals(text):
    out = []
    for m in NUM.finditer(clean_for_numbers(text)):
        raw = m.group(0).strip()
        num_s = m.group("num")
        val = float(num_s.replace(",", ""))
        dec = len(num_s.split(".")[1]) if "." in num_s else 0
        cur, unit = m.group("cur"), m.group("unit")
        neg = bool(m.group("neg"))
        if not cur and not unit:
            if 1900 <= val <= 2100 and dec == 0 and "," not in num_s:
                continue                      # a year
            if val <= 20 and dec == 0:
                continue                      # a count: top 10, three segments, 2 quarters
        kind, v, tol = classify(val, dec, cur, unit)
        out.append({"raw": raw, "value": -v if neg else v, "kind": kind, "tol": tol, "abs": v})
    return out


def classify(val, dec, cur, unit):
    step = 10 ** (-dec)
    u = (unit or "")
    if u == "%":
        return "pct", val / 100, step / 200 + 1e-9
    if u in ("pp", "bps"):
        f = 100 if u == "pp" else 10000
        return "pp", val / f, step / (2 * f) + 1e-9
    if u in ("x", "×"):
        return "x", val, step / 2 + 1e-9
    scale = {"B": 1000, "bn": 1000, "billion": 1000, "M": 1, "mn": 1, "million": 1, "T": 1e6, "trillion": 1e6, "K": 0.001}
    if u in scale:
        return "money", val * scale[u], step * scale[u] / 2 + 1e-9
    if cur:
        return "currency", val, step / 2 + 1e-9
    return "plain", val, step / 2 + 1e-9


UNIT_COMPAT = {
    "pct": {"pct"}, "pp": {"pp", "pct"}, "x": {"x"}, "money": {"money_m", "shares_m"},
    "currency": {"ps", "money_m"}, "plain": {"num", "days", "money_m", "shares_m", "ratio", "years", "x", "ps"},
}


def match_metrics(lit, values, context):
    compat = UNIT_COMPAT[lit["kind"]]
    words = set(re.findall(r"[a-z]{3,}", context.lower()))
    hits = []
    for key, rec in values.items():
        v = rec.get("v")
        if not isinstance(v, (int, float)) or rec.get("unit") not in compat or isinstance(v, bool):
            continue
        if math.isnan(v):
            continue
        a = abs(v)
        target = lit["abs"]
        tol = lit["tol"]
        if lit["kind"] == "plain" and rec.get("unit") == "money_m" and a >= 1000 and target < 1000:
            continue
        if abs(a - target) <= tol:
            label = (rec.get("label") or key).lower()
            score = len(words & set(re.findall(r"[a-z]{3,}", label + " " + key.replace("_", " "))))
            hits.append((score, key))
    hits.sort(key=lambda x: (-x[0], len(x[1])))
    related = [k for sc, k in hits if sc > 0]
    return related[:3], [k for _, k in hits[:3]]


# ---------------------------------------------------------------- tickers
def load_sec_names():
    path = os.path.join(os.path.expanduser("~"), ".cache", "stock-analysis-teardown", "company_tickers_exchange.json")
    data = read_json(path)
    if not data:
        return {}
    f = data["fields"]
    out = {}
    for row in data["data"]:
        rec = dict(zip(f, row))
        out[str(rec["ticker"]).upper()] = rec["name"]
    return out


TICKER_PAIR = re.compile(r"([A-Z][A-Za-z0-9&.'’\- ]{1,60}?)\s*\(\s*(?:[A-Z]+:\s*)?([A-Z0-9]{1,6}(?:[.-][A-Z]{1,3})?)\s*\)")
STOP = {"the", "and", "inc", "corp", "co", "ltd", "group", "holding", "holdings", "plc", "technology", "technologies"}


def name_matches(stated, official):
    s_words = [w for w in re.findall(r"[a-z0-9]+", stated.lower()) if w not in STOP]
    o = official.lower()
    o_words = re.findall(r"[a-z0-9]+", o)
    initials = "".join(w[0] for w in o_words if w)
    if not s_words:
        return True
    w = s_words[-1] if len(s_words) == 1 else s_words[0]
    return any(x in o for x in s_words) or w in initials or initials.startswith(w)


def check_tickers(text, where, sec_names, peer_names, issues):
    for m in TICKER_PAIR.finditer(TOKEN.sub(" ", text)):
        stated = m.group(1).strip()
        stated = re.split(r"[,;:]| and | vs | versus | than | with ", stated)[-1].strip()
        tick = m.group(2).upper()
        if len(stated) < 2 or tick in ("TTM", "GAAP", "FCF", "EPS", "ROIC", "CAGR", "TAM", "SBC", "AI", "US", "EU", "UK"):
            continue
        official = peer_names.get(tick) or sec_names.get(tick) or sec_names.get(tick.replace(".", "-"))
        if not official:
            issues.append(("warn", where, f"cannot verify ticker {tick} for '{stated}': not in the SEC list or peers.json"))
        elif not name_matches(stated, official):
            issues.append(("error", where, f"ticker {tick} belongs to '{official}', not '{stated}'"))


# ---------------------------------------------------------------- writing
def check_writing(text, where, kind, issues):
    t = TOKEN.sub("0", URL.sub("", text))
    if "\u2014" in t:
        issues.append(("error", where, "em dash; use a full stop, comma or parentheses"))
    if re.search(r"\s\u2013\s", t):
        issues.append(("error", where, "spaced en dash used as a dash; rewrite the sentence"))
    low = t.lower()
    for w in BANNED_ERR:
        if re.search(rf"\b{w}\b", low):
            issues.append(("error", where, f"banned word '{w}'; say the specific thing instead"))
    for w in BANNED_WARN:
        if w in low:
            issues.append(("warn", where, f"AI-sounding phrase '{w}'"))
    if kind in ("prose", "title") and LABEL_COLON.match(t):
        issues.append(("error", where, "label colon at the start ('The fix: ...'); use the bullet 'lead' field or two sentences"))
    if BY_ING.search(t):
        issues.append(("error", where, "'by doing X and Y' construction; say what happened as its own sentence"))
    d = DOUBLE.search(t)
    if d and d.group(1).lower() not in ("that", "had", "is"):
        issues.append(("warn", where, f"doubled word '{d.group(0)}'"))
    if "!" in t:
        issues.append(("warn", where, "exclamation mark"))
    if kind == "title":
        if len(t) > 95:
            issues.append(("warn", where, f"title is {len(t)} characters; aim for under 90"))
        if t.rstrip().endswith("."):
            issues.append(("warn", where, "action titles do not end with a full stop"))
    if kind == "prose" and len(t) > 240:
        issues.append(("warn", where, f"{len(t)} characters; split it or cut words"))


def colon_count(text):
    t = URL.sub("", TOKEN.sub("", text))
    t = re.sub(r"\d:\d", "", t)
    return t.count(":")


# ---------------------------------------------------------------- main check
def check(run_dir, deck_path=None):
    paths = run_paths(run_dir)
    deck_path = deck_path or os.path.join(paths["run"], "deck.json")
    deck = read_json(deck_path)
    if deck is None:
        sys.exit(f"cannot read {deck_path}")
    m = read_json(os.path.join(paths["data"], "metrics.json")) or {"values": {}}
    values = m.get("values", {})
    peers = read_json(os.path.join(paths["data"], "peers.json")) or {}
    peer_names = {r["ticker"].upper(): (r.get("legal_name") or r.get("name") or "") for r in peers.get("rows", [])}
    sec_names = load_sec_names()
    issues = []
    numbers = []
    meta = deck.get("meta") or {}

    for k in ("verdict", "verdict_line"):
        if meta.get(k):
            check_writing(meta[k], f"meta.{k}", "prose", issues)
            if VERDICT_WORDS.search(meta[k]):
                issues.append(("error", f"meta.{k}", f"rating language '{VERDICT_WORDS.search(meta[k]).group(0)}'; describe the view in words, no Buy/Sell/Hold"))
    if meta.get("subtitle"):
        check_writing(meta["subtitle"], "meta.subtitle", "prose", issues)

    for sl in deck.get("slides", []):
        sid = sl.get("id", "?")
        slide_has_refs = bool(sl.get("refs")) or any(r for _, _, r, _ in slide_elements(sl))
        colons = 0
        for field, text, refs, kind in slide_elements(sl):
            if not isinstance(text, str) or not text.strip():
                continue
            where = f"{sid}.{field}"
            check_writing(text, where, kind, issues)
            check_tickers(text, where, sec_names, peer_names, issues)
            if kind in ("prose", "title"):
                colons += colon_count(text)
            for lit in literals(text):
                sourced = bool(refs) or (kind in ("title", "label") and slide_has_refs) or (field in ("lead", "takeaway") and slide_has_refs)
                if refs == ["view"]:
                    numbers.append({"slide": sid, "field": field, "literal": lit["raw"], "sourced": True, "basis": "view"})
                    continue
                keys, loose = match_metrics(lit, values, text) if values else ([], [])
                rec = {"slide": sid, "field": field, "literal": lit["raw"], "sourced": sourced, "matches": keys or loose}
                numbers.append(rec)
                if keys:
                    issues.append(("warn", where, f"'{lit['raw']}' typed by hand; it matches {', '.join(keys)}. "
                                                  f"Use the token, e.g. {{{{m:{keys[0]}}}}}"))
                elif not sourced:
                    hint = f" (same value as {', '.join(loose)}: if that is what it means, use the token)" if loose else ""
                    issues.append(("error", where, f"'{lit['raw']}' has no source ref and matches no related computed metric{hint}"))
        if colons > 1:
            issues.append(("warn", sid, f"{colons} colons in the prose on this slide; the limit is one"))
        for i, ch in enumerate(sl.get("charts") or []):
            hand = []
            for s in ch.get("series") or []:
                if s.get("metric"):
                    continue
                hand += [x for x in s.get("data", []) if isinstance(x, (int, float)) or (isinstance(x, str) and not TOKEN.fullmatch(x.strip()))]
            for st in ch.get("steps") or []:
                v = st.get("value")
                if isinstance(v, (int, float)) or (isinstance(v, str) and not TOKEN.fullmatch(v.strip())):
                    hand.append(v)
            for p in ch.get("parts") or []:
                v = p.get("value")
                if isinstance(v, (int, float)):
                    hand.append(v)
            if hand and not (ch.get("refs") or ch.get("source")):
                issues.append(("error", f"{sid}.charts[{i}]", f"chart '{ch.get('title')}' has {len(hand)} hand-typed values and no refs or source"))
        t = sl.get("table") or {}
        if t and not t.get("from") and t.get("rows"):
            nums = [c for r in t["rows"] for c in r if isinstance(c, (int, float)) or (isinstance(c, str) and literals(c))]
            if nums and not t.get("refs"):
                issues.append(("error", f"{sid}.table", f"table has {len(nums)} hand-typed numbers and no refs"))
            for ri, r in enumerate(t["rows"]):
                for c in r:
                    if isinstance(c, str):
                        check_writing(c, f"{sid}.table.rows[{ri}]", "label", issues)
                        check_tickers(c, f"{sid}.table.rows[{ri}]", sec_names, peer_names, issues)

    # peers sanity
    rows = peers.get("rows", [])
    numeric_cols = [c["key"] for c in peers.get("columns", []) if c.get("unit") != "text"]
    for c in numeric_cols:
        seen = {}
        for r in rows:
            v = r.get(c)
            if isinstance(v, (int, float)) and v != 0:
                seen.setdefault(round(v, 4), []).append(r["ticker"])
        for v, ts in seen.items():
            if len(ts) > 1:
                issues.append(("warn", "peers.json", f"{c} is identical ({v}) for {', '.join(ts)}; check for a copy-paste error"))
    for r in rows:
        for c in ("gross_margin", "operating_margin", "net_margin", "fcf_margin"):
            v = r.get(c)
            if not isinstance(v, (int, float)):
                continue
            if c == "gross_margin" and not -1 <= v <= 1 or v > 5 or v < -20:
                # a gross margin above 100% cannot happen; a margin in the thousands of percent means a unit error
                issues.append(("error", "peers.json", f"{r['ticker']} {c} = {v}: not a possible margin (margins are "
                                                     f"fractions, 0.51 = 51%); check the units"))
            elif not -1 <= v <= 1:
                # a real one-off can do this (Lumentum's -230% net margin came from a non-cash debt loss)
                issues.append(("warn", "peers.json", f"{r['ticker']} {c} = {v:.0%}: outside -100%..100%. Confirm the "
                                                    f"one-off behind it and say so wherever the peer is compared"))
        pe = r.get("pe_ttm")
        if isinstance(pe, (int, float)) and pe > 400:
            issues.append(("warn", "peers.json", f"{r['ticker']} P/E {pe:.0f}x; check EPS units and the share count"))
        if r.get("manual") and not (r.get("sources") or r.get("source")):
            issues.append(("error", "peers.json", f"{r['ticker']} was entered by hand without sources"))

    return issues, numbers


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--deck")
    ap.add_argument("--json")
    a = ap.parse_args()
    issues, numbers = check(a.run_dir, a.deck)
    errs = [i for i in issues if i[0] == "error"]
    warns = [i for i in issues if i[0] == "warn"]
    out = a.json or os.path.join(run_paths(a.run_dir)["build"], "check_numbers.json")
    write_json(out, {"errors": len(errs), "warnings": len(warns),
                     "issues": [{"level": l, "where": w, "msg": m} for l, w, m in issues], "literals": numbers})
    for l, w, msg in errs + warns:
        print(f"{l.upper():5} {w}: {msg}")
    print(f"\n{len(numbers)} hand-typed numbers checked; {len(errs)} errors, {len(warns)} warnings -> {out}")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
