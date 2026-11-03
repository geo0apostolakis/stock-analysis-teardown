#!/usr/bin/env python3
"""Pull a company's financial statements and key filings from SEC EDGAR (free, no key).

usage:
  fetch_sec.py RUN_DIR [--what facts,filings,insiders] [--refresh]
  fetch_sec.py RUN_DIR --cik 1730168 --dest RUN_DIR/data/peers/AVGO --what facts   (peers)

Writes into <dest> (default RUN_DIR/data):
  statements.json   annual (up to 10 fiscal years), quarterly, TTM, latest balance sheet,
                    every value with the XBRL tag, accession number, form and filing date
  filings/          latest 10-K or 20-F as text plus one file per Item, latest 10-Q,
                    latest proxy (DEF 14A), the last four earnings releases (8-K Item 2.02, EX-99.1)
  filings/index.json   what was downloaded, with SEC URLs to cite
  insiders.json     Form 4 transactions for the last 12 months, summarised per insider

Rules this script follows (each one fixes a real mistake):
  * Periods are keyed by end date and duration, never by the XBRL `frame` field.
    `frame` is calendar-based, so Marvell's fiscal 2026 (ends Jan 31 2026) shows up as CY2025.
  * Fiscal year labels come from the 10-K/20-F that reports the period as its main year.
  * When a period is restated, the most recently filed value wins.
  * Each line item walks a chain of tags (see concepts.py), chosen per period.
"""
import argparse
import datetime as dt
import html
import os
import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (cached_json, filing_doc_url, filing_index_url, get_json, http_get,  # noqa: E402
                     log, parse_date, read_json, run_paths, today, update_run, write_json, write_text)
from concepts import ANNUAL_FORMS, CONCEPTS  # noqa: E402

MAX_YEARS = 10


# ---------------------------------------------------------------- XBRL facts

def pick_taxonomy(facts):
    g = facts.get("facts", {})
    us, ifrs = len(g.get("us-gaap", {})), len(g.get("ifrs-full", {}))
    return "ifrs-full" if ifrs > us else "us-gaap"


def pick_currency(facts, taxonomy):
    g = facts["facts"].get(taxonomy, {})
    counts = {}
    for tag in CONCEPTS["revenue"][taxonomy] + ["Assets"]:
        for unit, rows in g.get(tag, {}).get("units", {}).items():
            if "/" in unit or unit in ("shares", "pure"):
                continue
            n = sum(1 for r in rows if r.get("form") in ANNUAL_FORMS)
            counts[unit] = counts.get(unit, 0) + n
    if not counts:
        return "USD"
    return max(counts.items(), key=lambda kv: kv[1])[0]


def rows_for(facts, taxonomy, tag, kind, currency):
    node = facts["facts"].get(taxonomy, {}).get(tag) or (
        facts["facts"].get("dei", {}).get(tag) if kind == "shares_i" else None)
    if not node:
        return []
    units = node.get("units", {})
    if kind in ("flow", "instant"):
        rows = units.get(currency, [])
    elif kind == "per_share":
        rows = units.get(f"{currency}/shares", [])
    else:
        rows = units.get("shares", [])
    out = []
    for r in rows:
        if "val" not in r or "end" not in r:
            continue
        rr = dict(r)
        rr["tag"] = tag
        rr["dur"] = (parse_date(r["end"]) - parse_date(r["start"])).days if r.get("start") else None
        out.append(rr)
    return out


def fiscal_calendar(facts, taxonomy, currency):
    """One entry per fiscal year, built from each annual report's main period."""
    by_accn = {}
    g = facts["facts"].get(taxonomy, {})
    probe_tags = CONCEPTS["revenue"][taxonomy] + CONCEPTS["net_income"][taxonomy] + CONCEPTS["cfo"][taxonomy]
    for tag in probe_tags:
        for unit, rows in g.get(tag, {}).get("units", {}).items():
            if unit != currency:
                continue
            for r in rows:
                if r.get("form") not in ANNUAL_FORMS or not r.get("start"):
                    continue
                dur = (parse_date(r["end"]) - parse_date(r["start"])).days
                if not 340 <= dur <= 380:
                    continue
                cur = by_accn.get(r["accn"])
                if cur is None or r["end"] > cur["end"]:
                    by_accn[r["accn"]] = {"start": r["start"], "end": r["end"], "fy": r.get("fy"),
                                          "form": r["form"], "filed": r["filed"], "accn": r["accn"]}
    periods = {}
    for p in by_accn.values():
        cur = periods.get(p["end"])
        # an amended report can repeat the period; keep the original annual filing for labelling
        if cur is None or (p["form"] in ("10-K", "20-F", "40-F") and cur["form"].endswith("/A")):
            periods[p["end"]] = p
    # Comparative-only years (older than the first 10-K in companyfacts) are added from rows directly
    for tag in CONCEPTS["revenue"][taxonomy]:
        for r in g.get(tag, {}).get("units", {}).get(currency, []):
            if r.get("form") not in ANNUAL_FORMS or not r.get("start"):
                continue
            dur = (parse_date(r["end"]) - parse_date(r["start"])).days
            if 340 <= dur <= 380 and r["end"] not in periods:
                periods[r["end"]] = {"start": r["start"], "end": r["end"], "fy": None, "form": r["form"],
                                     "filed": r["filed"], "accn": r["accn"], "inferred": True}
    out = []
    for end in sorted(periods):
        p = periods[end]
        fy = p.get("fy")
        inferred = p.get("inferred", False) or not fy
        if inferred:
            fy = parse_date(end).year
        out.append({"label": f"FY{fy}", "fy": fy, "start": p["start"], "end": end, "form": p["form"],
                    "accn": p["accn"], "filed": p["filed"], "label_inferred": inferred})
    # de-duplicate labels (rare; can happen around fiscal-year changes)
    seen = {}
    for p in out:
        if p["label"] in seen:
            p["label"] = f"FY{p['fy']}-{p['end'][5:7]}"
        seen[p["label"]] = True
    return out[-MAX_YEARS:]


def best_row(rows):
    """Most recently filed wins; annual forms break ties."""
    return max(rows, key=lambda r: (r.get("filed", ""), r.get("form") in ANNUAL_FORMS))


def close_dates(a, b, tol=4):
    return abs((parse_date(a) - parse_date(b)).days) <= tol


def value_for_period(rows, kind, start, end):
    if kind in ("instant", "shares_i"):
        cands = [r for r in rows if r["dur"] is None and r["end"] == end]
        if not cands:
            cands = [r for r in rows if r["dur"] is None and close_dates(r["end"], end)]
        if kind == "shares_i" and cands:
            # several share classes reported in the same filing are summed
            best = best_row(cands)
            same = [r for r in cands if r["accn"] == best["accn"] and r["end"] == best["end"]]
            if len(same) > 1:
                total = dict(best)
                total["val"] = sum(r["val"] for r in same)
                total["classes"] = len(same)
                return total
        return best_row(cands) if cands else None
    cands = [r for r in rows if r["dur"] is not None and r["end"] == end and close_dates(r["start"], start)]
    if not cands:
        cands = [r for r in rows if r["dur"] is not None and close_dates(r["end"], end) and close_dates(r["start"], start)]
    return best_row(cands) if cands else None


def item_values(facts, taxonomy, currency, key, spec, periods):
    """Walk the tag chain per period. Revenue takes the largest candidate (total, not a component)."""
    chain = spec.get(taxonomy, [])
    if spec["kind"] == "shares_i":
        chain = chain + ["EntityCommonStockSharesOutstanding"]
    all_rows = {tag: rows_for(facts, taxonomy, tag, spec["kind"], currency) for tag in chain}
    out = {}
    for p in periods:
        picked = None
        cands = []
        for tag in chain:
            r = value_for_period(all_rows[tag], spec["kind"], p["start"], p["end"])
            if r is not None:
                cands.append(r)
                if key != "revenue":
                    picked = r
                    break
        if key == "revenue" and cands:
            picked = max(cands, key=lambda r: r["val"])
        if picked is not None:
            out[p["label"]] = {"v": picked["val"], "tag": picked["tag"], "accn": picked["accn"],
                               "form": picked.get("form"), "filed": picked.get("filed"), "end": picked["end"]}
    return out, all_rows


def cumulative_points(rows_by_tag, chain, fy_start, take_max=False):
    """Cumulative values from a fiscal-year start (3M, 6M, 9M, 12M) for one flow item.
    Companies switch tags between the 10-Q and the 10-K (Lumentum tags 10-Q revenue IncludingAssessedTax and
    10-K revenue ExcludingAssessedTax), so points are merged across the chain by period end. For one end date the
    earlier tag in the chain wins, except revenue, where the largest value wins as it does for annual figures."""
    best = {}
    for rank, tag in enumerate(chain):
        for r in rows_by_tag.get(tag, []):
            if r["dur"] is None or r["dur"] < 60 or not close_dates(r["start"], fy_start):
                continue
            cur = best.get(r["end"])
            if cur is None:
                best[r["end"]] = (rank, r)
                continue
            crank, cr = cur
            newer = r.get("filed", "") > cr.get("filed", "")
            if take_max:
                if r["val"] > cr["val"] or (r["val"] == cr["val"] and newer):
                    best[r["end"]] = (rank, r)
            elif rank < crank or (rank == crank and newer):
                best[r["end"]] = (rank, r)
    return [best[k][1] for k in sorted(best)]


def build_quarters_and_ttm(facts, taxonomy, currency, periods, items_rows):
    """Quarterly flow values via differences of cumulative fiscal-year-to-date figures."""
    if not periods:
        return {"periods": [], "items": {}}, {"items": {}}
    last = periods[-1]
    next_start = (parse_date(last["end"]) + dt.timedelta(days=1)).isoformat()
    fy_starts = [(p["start"], p["label"], p["fy"]) for p in periods[-3:]]
    fy_starts.append((next_start, f"FY{(last['fy'] or parse_date(last['end']).year) + 1}", None))

    q_periods = {}
    q_items = {}
    ttm = {}
    ttm_meta = {"base": last["label"], "base_end": last["end"]}
    item_end = {}
    for key, spec in CONCEPTS.items():
        if spec["kind"] != "flow":
            continue
        chain = spec.get(taxonomy, [])
        rows_by_tag = items_rows.get(key, {})
        vals = {}
        cum_by_fy = {}
        for fy_start, fy_label, _ in fy_starts:
            pts = cumulative_points(rows_by_tag, chain, fy_start, take_max=(key == "revenue"))
            cum_by_fy[fy_label] = pts
            prev_v, prev_end, prev_q = 0.0, None, 0
            for r in pts:
                qn = max(1, round((r["dur"] or 0) / 91.3))
                # a quarter is only derived from the cumulative figure just before it. With the nine-month
                # figure missing, "Q4" would be the whole year.
                if qn <= 4 and (r["dur"] or 0) <= 380 and qn == prev_q + 1:
                    label = f"Q{qn} {fy_label}"
                    start = fy_start if prev_end is None else (parse_date(prev_end) + dt.timedelta(days=1)).isoformat()
                    q_periods[label] = {"label": label, "start": start, "end": r["end"]}
                    vals[label] = {"v": r["val"] - prev_v, "derived": prev_q > 0, "tag": r["tag"]}
                prev_v, prev_end, prev_q = r["val"], r["end"], qn
        if vals:
            q_items[key] = {"label": spec["label"], "values": vals}
        # TTM = last full year + current year-to-date - same period last year
        cur_label = fy_starts[-1][1]
        cur_pts = cum_by_fy.get(cur_label) or []
        base_pts = cum_by_fy.get(last["label"]) or []
        base_full = next((r for r in base_pts if 340 <= (r["dur"] or 0) <= 380), None)
        if base_full is None:
            continue
        if cur_pts:
            latest = cur_pts[-1]
            prior = next((r for r in base_pts if abs((r["dur"] or 0) - (latest["dur"] or 0)) <= 7), None)
            if prior is not None:
                ttm[key] = base_full["val"] + latest["val"] - prior["val"]
                item_end[key] = latest["end"]
                continue
        ttm[key] = base_full["val"]
        item_end[key] = base_full["end"]
    if item_end:
        as_of = max(item_end.values())
        ttm_meta["as_of"] = as_of
        ttm_meta["method"] = (f"{last['label']} + YTD to {as_of} - prior-year YTD" if as_of > last["end"]
                              else f"{last['label']} (no later quarter filed)")
        cur = lambda k: k in item_end and close_dates(item_end[k], as_of, tol=10)  # noqa: E731
        if not cur("pretax_income") and cur("net_income") and cur("income_tax"):
            # some 10-Qs do not tag pre-tax income (Marvell); net income + income tax gives the same line
            ttm["pretax_income"] = ttm["net_income"] + ttm["income_tax"]
            item_end["pretax_income"] = as_of
            ttm_meta["derived"] = {"pretax_income": "net_income + income_tax"}
        behind = {k: e for k, e in item_end.items() if not cur(k)}
        if behind:
            ttm_meta["items_behind"] = behind
    # latest diluted / basic share counts from the most recent report (any length of period)
    for key in ("shares_diluted", "shares_basic"):
        rows = [r for rs in items_rows.get(key, {}).values() for r in rs if (r["dur"] or 0) >= 60]
        if rows:
            r = max(rows, key=lambda r: (r["end"], r.get("filed", "")))
            ttm[key] = r["val"]
            ttm_meta[f"{key}_period_end"] = r["end"]
    ordered = sorted(q_periods.values(), key=lambda p: p["end"])[-12:]
    keep = {p["label"] for p in ordered}
    for k in q_items:
        q_items[k]["values"] = {lbl: v for lbl, v in q_items[k]["values"].items() if lbl in keep}
    return {"periods": ordered, "items": q_items}, {"items": ttm, **ttm_meta}


def _sum_parts(vals, checks=None, when=None):
    """vals maps item key -> {"v": ...} for one balance sheet date. A debt line with no single total tag is the
    sum of its parts (current portion + short-term borrowings; bonds + loans). Two parts with the same value are
    the same line tagged twice, so they count once. Every real sum is logged as a check for the data-room agent."""
    for key, spec in CONCEPTS.items():
        if "parts" not in spec or key in vals:
            continue
        parts = []
        for k in spec["parts"]:
            if k in vals and not any(abs(vals[k]["v"] - q["v"]) <= 0.005 * max(abs(q["v"]), 1) for q in parts):
                parts.append(vals[k])
        if not parts:
            continue
        vals[key] = {**parts[0], "v": sum(q["v"] for q in parts), "tag": " + ".join(q["tag"] for q in parts)}
        if len(parts) > 1 and checks is not None:
            amounts = " + ".join(f"{q['v'] / 1e6:,.0f}M" for q in parts)
            checks.append(f"{spec['label']} at {when} is the sum of {vals[key]['tag']} ({amounts}). "
                          f"Confirm it against the balance sheet.")


def latest_balance(facts, taxonomy, currency):
    out = {}
    latest_end = None
    for key, spec in CONCEPTS.items():
        if spec["kind"] not in ("instant", "shares_i") or key.startswith("maturity"):
            continue
        # newest value across the whole chain: companies switch tags over the years, and an old tag that
        # stopped in 2023 must not hide the one they use now. Ties go to the earlier tag in the chain.
        best = None
        for rank, tag in enumerate(spec.get(taxonomy, [])):
            rows = [r for r in rows_for(facts, taxonomy, tag, spec["kind"], currency) if r["dur"] is None]
            if rows:
                r = max(rows, key=lambda r: (r["end"], r.get("filed", "")))
                if best is None or r["end"] > best[1]["end"] and not close_dates(r["end"], best[1]["end"], tol=10):
                    best = (tag, r)
        if best:
            tag, r = best
            out[key] = {"v": r["val"], "tag": tag, "end": r["end"], "accn": r["accn"], "form": r.get("form"),
                        "filed": r.get("filed")}
            latest_end = max(latest_end or r["end"], r["end"])
    # Only keep values from the most recent balance sheet date so the snapshot is consistent
    if latest_end:
        out = {k: v for k, v in out.items() if close_dates(v["end"], latest_end, tol=10) or k == "shares_outstanding"}
    checks = []
    if latest_end:
        _sum_parts(out, checks, latest_end)
    dei = facts["facts"].get("dei", {}).get("EntityCommonStockSharesOutstanding", {}).get("units", {}).get("shares", [])
    if dei:
        last_end = max(r["end"] for r in dei)
        last_rows = [r for r in dei if r["end"] == last_end]
        best_accn = max(last_rows, key=lambda r: r.get("filed", ""))["accn"]
        total = sum(r["val"] for r in last_rows if r["accn"] == best_accn)
        out["shares_outstanding_cover"] = {"v": total, "end": last_end, "tag": "dei:EntityCommonStockSharesOutstanding",
                                           "accn": best_accn, "classes": sum(1 for r in last_rows if r["accn"] == best_accn)}
    return {"date": latest_end, "items": out, "checks": checks}


def debt_maturities(facts, taxonomy, currency):
    """Scheduled principal by year from the newest complete schedule. 10-Qs often give only the next four years
    (Marvell's does), so a schedule with the after-year-five bucket wins over a newer one without it."""
    keys = ("maturity_y1", "maturity_y2", "maturity_y3", "maturity_y4", "maturity_y5", "maturity_after5")
    by_end = {}
    for key in keys:
        for tag in CONCEPTS[key].get(taxonomy, []):
            for r in rows_for(facts, taxonomy, tag, "instant", currency):
                if r["dur"] is not None:
                    continue
                cur = by_end.setdefault(r["end"], {}).get(key)
                if cur is None or r.get("filed", "") > cur.get("filed", ""):
                    by_end[r["end"]][key] = {"v": r["val"], "end": r["end"], "accn": r["accn"], "filed": r.get("filed")}
    if not by_end:
        return None
    ends = sorted(by_end, reverse=True)
    as_of = next((e for e in ends if "maturity_after5" in by_end[e]), ends[0])
    return {"as_of": as_of, "items": by_end[as_of], "complete": "maturity_after5" in by_end[as_of]}


def build_statements(facts, identity):
    taxonomy = pick_taxonomy(facts)
    currency = pick_currency(facts, taxonomy)
    periods = fiscal_calendar(facts, taxonomy, currency)
    items, items_rows, gaps = {}, {}, []
    for key, spec in CONCEPTS.items():
        if key.startswith("maturity"):
            continue
        vals, rows = item_values(facts, taxonomy, currency, key, spec, periods)
        items_rows[key] = rows
        if vals:
            items[key] = {"label": spec["label"], "kind": spec["kind"], "values": vals}
        missing = [p["label"] for p in periods[-6:] if p["label"] not in vals]
        if missing:
            gaps.append({"item": key, "missing": missing})
    summed = {}
    part_keys = {k for spec in CONCEPTS.values() for k in spec.get("parts", [])}
    for p in periods:
        one = {k: items[k]["values"][p["label"]] for k in items if (k in part_keys or "parts" in CONCEPTS.get(k, {}))
               and p["label"] in items[k]["values"]}
        before = set(one)
        _sum_parts(one)
        for k in set(one) - before:
            summed.setdefault(k, {})[p["label"]] = one[k]
    for k, vals in summed.items():
        # add the summed years to the years that had a total tag; never replace them
        items.setdefault(k, {"label": CONCEPTS[k]["label"], "kind": "instant", "values": {}})["values"].update(vals)
        have = items[k]["values"]
        gaps = [g for g in gaps if g["item"] != k]
        m = [p["label"] for p in periods[-6:] if p["label"] not in have]
        if m:
            gaps.append({"item": k, "missing": m})
    quarterly, ttm = build_quarters_and_ttm(facts, taxonomy, currency, periods, items_rows)
    filings = {}
    for item in items.values():
        for v in item["values"].values():
            if v.get("accn"):
                filings[v["accn"]] = {"accn": v["accn"], "form": v.get("form"), "filed": v.get("filed"),
                                      "url": filing_index_url(identity["cik"], v["accn"])}
    return {
        "meta": {
            "ticker": identity.get("ticker"), "cik": identity.get("cik"), "name": facts.get("entityName"),
            "taxonomy": taxonomy, "currency": currency, "source": "SEC XBRL companyfacts API",
            "source_url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(identity['cik']):010d}.json",
            "generated": today(), "units": "raw (currency units, shares, currency per share)",
        },
        "annual": {"periods": periods, "items": items},
        "quarterly": quarterly,
        "ttm": ttm,
        "latest_balance": latest_balance(facts, taxonomy, currency),
        "debt_maturities": debt_maturities(facts, taxonomy, currency),
        "filings_used": sorted(filings.values(), key=lambda f: f["filed"] or ""),
        "gaps": gaps,
    }


# ---------------------------------------------------------------- filing text

class _TextExtractor(HTMLParser):
    BLOCK = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "section", "title"}
    SKIP = {"script", "style", "head"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip_depth, self.hidden_depth = [], 0, 0
        self.stack = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        a = dict(attrs)
        hidden = tag == "ix:header" or "display:none" in (a.get("style") or "").replace(" ", "").lower()
        self.stack.append((tag, hidden))
        if hidden:
            self.hidden_depth += 1
        if tag in self.SKIP:
            self.skip_depth += 1
        if tag in self.BLOCK:
            self.parts.append("\n")
        elif tag in ("td", "th"):
            self.parts.append(" | ")

    def handle_endtag(self, tag):
        tag = tag.lower()
        while self.stack:
            t, hidden = self.stack.pop()
            if hidden:
                self.hidden_depth -= 1
            if t in self.SKIP:
                self.skip_depth -= 1
            if t == tag:
                break
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.skip_depth or self.hidden_depth:
            return
        self.parts.append(data)


def html_to_text(raw):
    p = _TextExtractor()
    try:
        p.feed(raw)
    except Exception:
        return re.sub(r"<[^>]+>", " ", html.unescape(raw))
    text = "".join(p.parts).replace("\xa0", " ")
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"[ \t]+", " ", line).strip(" |\t")
        line = re.sub(r"(?: \| ){2,}", " | ", line)  # empty spacer cells in tables
        if line:
            lines.append(line)
    return "\n".join(lines)


ITEM_RE = re.compile(r"^item\s+(\d{1,2}[a-d]?)\s*[\.:\-—–]?\s*(.{0,120})$", re.I)


def split_items(text):
    """Split a 10-K/20-F into its Items. The table of contents also matches, so for each Item
    we keep the occurrence followed by the most text."""
    lines = text.split("\n")
    heads = []
    for i, line in enumerate(lines):
        m = ITEM_RE.match(line.strip())
        if m and len(line) < 160:
            heads.append((i, m.group(1).upper()))
    best = {}
    for idx, (i, key) in enumerate(heads):
        end = heads[idx + 1][0] if idx + 1 < len(heads) else len(lines)
        size = sum(len(x) for x in lines[i:end])
        if key not in best or size > best[key][2]:
            best[key] = (i, end, size)
    return {k: "\n".join(lines[s:e]) for k, (s, e, _) in best.items() if e - s > 3}


def download_doc(cik, accn, doc, dest_txt, refresh=False):
    if os.path.exists(dest_txt) and not refresh:
        with open(dest_txt) as f:
            return f.read()
    raw = http_get(filing_doc_url(cik, accn, doc)).decode("utf-8", errors="replace")
    text = html_to_text(raw) if doc.lower().endswith((".htm", ".html")) else raw
    write_text(dest_txt, text)
    return text


def fetch_filings(identity, dest, refresh=False, as_of=None):
    """Latest annual report, 10-Q, proxy and earnings releases filed on or before the run's as-of date, so a
    resumed run never mixes in a filing that came out after the price date."""
    as_of = as_of or dt.date.today().isoformat()
    cik = identity["cik"]
    sub = cached_json(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json",
                      os.path.join(dest, "sec", "submissions.json"), refresh=refresh)
    rec = sub["filings"]["recent"]
    rows = [dict(zip(rec.keys(), vals)) for vals in zip(*rec.values())]
    rows = [r for r in rows if r["filingDate"] <= as_of]
    fdir = os.path.join(dest, "filings")
    index = []

    def take(forms, n=1, pred=None):
        hits = [r for r in rows if r["form"] in forms and (pred is None or pred(r))]
        return hits[:n]

    annual = take({"10-K", "20-F", "40-F"}, 1)
    for r in annual:
        name = f"{r['form'].replace('/', '')}-{r['filingDate']}"
        text = download_doc(cik, r["accessionNumber"], r["primaryDocument"], os.path.join(fdir, name + ".txt"), refresh)
        items = split_items(text)
        for k, body in items.items():
            write_text(os.path.join(fdir, f"{name}-item{k}.txt"), body)
        index.append({"kind": "annual_report", "form": r["form"], "filed": r["filingDate"],
                      "period": r.get("reportDate"), "accn": r["accessionNumber"], "file": name + ".txt",
                      "items": sorted(items.keys(), key=lambda s: (int(re.match(r"\d+", s).group()), s)),
                      "url": filing_doc_url(cik, r["accessionNumber"], r["primaryDocument"])})
    for r in take({"10-Q"}, 1):
        name = f"10-Q-{r['filingDate']}"
        download_doc(cik, r["accessionNumber"], r["primaryDocument"], os.path.join(fdir, name + ".txt"), refresh)
        index.append({"kind": "quarterly_report", "form": "10-Q", "filed": r["filingDate"], "period": r.get("reportDate"),
                      "accn": r["accessionNumber"], "file": name + ".txt",
                      "url": filing_doc_url(cik, r["accessionNumber"], r["primaryDocument"])})
    for r in take({"DEF 14A"}, 1):
        name = f"DEF14A-{r['filingDate']}"
        download_doc(cik, r["accessionNumber"], r["primaryDocument"], os.path.join(fdir, name + ".txt"), refresh)
        index.append({"kind": "proxy", "form": "DEF 14A", "filed": r["filingDate"], "accn": r["accessionNumber"],
                      "file": name + ".txt", "url": filing_doc_url(cik, r["accessionNumber"], r["primaryDocument"])})
    # earnings releases: 8-K Item 2.02 (or 6-K for foreign issuers), exhibit 99.1
    # A deal announcement can carry Item 2.02 too (Marvell's Lumentum release did, with preliminary results), so
    # only releases that are mainly results count toward the four quarters; the others are kept as extras.
    deal_re = re.compile(r"definitive (merger |acquisition )?agreement|agreed to acquire|to acquire .{0,80} in an? "
                         r"(all-stock|all-cash|cash and stock|stock) transaction|merger agreement", re.I)
    plain = 0
    for r in take({"8-K"}, 10, pred=lambda r: "2.02" in (r.get("items") or "")):
        if plain >= 4:
            break
        other = sorted(set(re.findall(r"\d\.\d\d", r.get("items") or "")) - {"2.02", "7.01", "9.01"})
        try:
            idx = get_json(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{r['accessionNumber'].replace('-', '')}/index.json")
            names = [it["name"] for it in idx.get("directory", {}).get("item", [])]
            ex = next((n for n in names if re.search(r"ex-?99[\._-]?0?1", n, re.I) and n.lower().endswith((".htm", ".html", ".txt"))), None)
            if not ex:
                continue
            tmp = os.path.join(fdir, f"8-K-{r['accessionNumber']}.txt")
            text = download_doc(cik, r["accessionNumber"], ex, tmp, refresh)
            deal = bool(deal_re.search(text[:4000]))
            mixed = bool(other) or deal
            name = f"8-K-earnings-{r['filingDate']}" if not mixed else f"8-K-release-{r['filingDate']}"
            os.replace(tmp, os.path.join(fdir, name + ".txt"))
            index.append({"kind": "earnings_release" if not mixed else "release_with_other_news",
                          "form": "8-K EX-99.1", "filed": r["filingDate"], "items": r.get("items"),
                          **({"note": "announces a deal as well as results"} if deal else {}),
                          "accn": r["accessionNumber"], "file": name + ".txt",
                          "url": filing_doc_url(cik, r["accessionNumber"], ex)})
            plain += not mixed
        except Exception as e:
            log("earnings release skipped:", r["accessionNumber"], e)
    # all 8-Ks of the last 18 months, listed (not downloaded) so agents can spot M&A and leadership changes
    cutoff = (parse_date(as_of) - dt.timedelta(days=548)).isoformat()
    events = [{"filed": r["filingDate"], "items": r.get("items"), "accn": r["accessionNumber"],
               "url": filing_doc_url(cik, r["accessionNumber"], r["primaryDocument"])}
              for r in rows if r["form"] == "8-K" and r["filingDate"] >= cutoff]
    write_json(os.path.join(fdir, "index.json"), {"documents": index, "recent_8k": events,
                                                  "item_codes": "2.01 acquisition/disposal, 2.02 results, 5.02 officer/director change, 1.01 material agreement, 8.01 other"})
    return index


# ---------------------------------------------------------------- insiders (Form 4)

def _x(node, path):
    el = node.find(path)
    return el.text.strip() if el is not None and el.text else None


def fetch_insiders(identity, dest, refresh=False, days=365, cap=200, as_of=None):
    cik = identity["cik"]
    sub = read_json(os.path.join(dest, "sec", "submissions.json")) or cached_json(
        f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", os.path.join(dest, "sec", "submissions.json"))
    rec = sub["filings"]["recent"]
    rows = [dict(zip(rec.keys(), vals)) for vals in zip(*rec.values())]
    end = as_of or dt.date.today().isoformat()
    cutoff = (parse_date(end) - dt.timedelta(days=days)).isoformat()
    f4 = [r for r in rows if r["form"] == "4" and cutoff <= r["filingDate"] <= end][:cap]
    cache_dir = os.path.join(dest, "sec", "form4")
    txs = []
    other_issuer = 0
    for r in f4:
        doc = r["primaryDocument"].split("/")[-1]
        path = os.path.join(cache_dir, r["accessionNumber"] + ".xml")
        try:
            if os.path.exists(path) and not refresh:
                raw = open(path, "rb").read()
            else:
                raw = http_get(filing_doc_url(cik, r["accessionNumber"], doc))
                os.makedirs(cache_dir, exist_ok=True)
                open(path, "wb").write(raw)
            root = ET.fromstring(raw)
        except Exception as e:
            log("form 4 skipped:", r["accessionNumber"], e)
            continue
        issuer_cik = _x(root, "issuer/issuerCik")
        if issuer_cik and int(issuer_cik) != int(cik):
            # the company itself reporting as an owner of another issuer (Coca-Cola selling a bottler stake)
            other_issuer += 1
            continue
        owner = _x(root, "reportingOwner/reportingOwnerId/rptOwnerName")
        rel = root.find("reportingOwner/reportingOwnerRelationship")
        role = []
        if rel is not None:
            if _x(rel, "isDirector") in ("1", "true"):
                role.append("Director")
            if _x(rel, "isOfficer") in ("1", "true"):
                role.append(_x(rel, "officerTitle") or "Officer")
            if _x(rel, "isTenPercentOwner") in ("1", "true"):
                role.append("10% owner")
        plan = _x(root, "aff10b5One") in ("1", "true")
        for t in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
            code = _x(t, "transactionCoding/transactionCode")
            shares = float(_x(t, "transactionAmounts/transactionShares/value") or 0)
            price = float(_x(t, "transactionAmounts/transactionPricePerShare/value") or 0)
            txs.append({
                "date": _x(t, "transactionDate/value"), "owner": owner, "role": ", ".join(role) or None,
                "code": code, "acq_disp": _x(t, "transactionAmounts/transactionAcquiredDisposedCode/value"),
                "shares": shares, "price": price, "value": round(shares * price, 2),
                "owned_after": float(_x(t, "postTransactionAmounts/sharesOwnedFollowingTransaction/value") or 0),
                "rule_10b5_1": plan, "accn": r["accessionNumber"],
                "url": filing_doc_url(cik, r["accessionNumber"], r["primaryDocument"]),
            })
    people = {}
    for t in txs:
        p = people.setdefault(t["owner"], {"owner": t["owner"], "role": t["role"], "open_market_buys": 0.0,
                                           "open_market_sells": 0.0, "buy_count": 0, "sell_count": 0,
                                           "latest_owned": None, "latest_date": None})
        if t["code"] == "P":
            p["open_market_buys"] += t["value"]
            p["buy_count"] += 1
        elif t["code"] == "S":
            p["open_market_sells"] += t["value"]
            p["sell_count"] += 1
        if t["date"] and (p["latest_date"] is None or t["date"] >= p["latest_date"]):
            p["latest_date"], p["latest_owned"] = t["date"], t["owned_after"]
    summary = {
        "window_days": days, "filings_read": len(f4), "transactions": len(txs),
        "skipped_other_issuer": other_issuer,
        "note": ("Form 4s where this company is the reporting owner of another issuer are left out."
                 if other_issuer else None),
        "open_market_buys_total": round(sum(p["open_market_buys"] for p in people.values()), 2),
        "open_market_sells_total": round(sum(p["open_market_sells"] for p in people.values()), 2),
        "codes": "P open-market buy, S open-market sale, A award, M option exercise, F tax withholding, G gift",
        "by_insider": sorted(people.values(), key=lambda p: -(p["open_market_sells"] + p["open_market_buys"])),
    }
    write_json(os.path.join(dest, "insiders.json"), {"summary": summary, "transactions": txs,
                                                       "source": "SEC Form 4 filings (EDGAR)"})
    return summary


# ---------------------------------------------------------------- ADR ratio

_WORDNUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
            "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "twenty-five": 25, "thirty": 30,
            "forty": 40, "fifty": 50, "hundred": 100, "one hundred": 100,
            "one-half": 0.5, "one half": 0.5, "half": 0.5, "one-third": 1 / 3, "one-quarter": 0.25,
            "one-fourth": 0.25, "one-fifth": 0.2, "one-tenth": 0.1}
_NUM = r"(?P<n>\d+(?:\.\d+)?|[a-z]+(?:[- ][a-z]+)?)(?:\s*\((?P<p>\d+(?:\.\d+)?)\))?"
_SH = r"(?:of\s+(?:one|an?)\s+)?(?:fully[- ]paid\s+)?(?:class\s+[a-z]\s+)?(?:common|ordinary|equity)\s+shares?"
_ADS = r"(?:ADSs?|ADRs?|American\s+Depositary\s+(?:Shares?|Receipts?))"
_ADR_RES = [
    re.compile(r"(?:each|one|every|1)\s+" + _ADS + r"\s*(?:\([^)]{0,25}\)\s*)?(?:currently\s+)?"
               r"(?:represents?|representing|is\s+equal\s+to|equals|corresponds\s+to)\s+" + _NUM + r"\s+" + _SH, re.I),
    re.compile(_ADS + r"\s*(?:\([^)]{0,25}\)\s*)?,?\s+each\s+(?:of\s+which\s+)?(?:currently\s+)?"
               r"represent(?:s|ing)\s+" + _NUM + r"\s+" + _SH, re.I),
    re.compile(_NUM + r"\s+" + _SH + r"\s+(?:per|for\s+each|to\s+one|for\s+one)\s+" + _ADS, re.I),
]


def _num(m):
    if m.group("p"):
        return float(m.group("p"))
    n = m.group("n").lower()
    if re.fullmatch(r"\d+(?:\.\d+)?", n):
        return float(n)
    if n in _WORDNUM:
        return float(_WORDNUM[n])
    first = n.split()[0].split("-")[0]
    return float(_WORDNUM[first]) if first in _WORDNUM else None


def adr_ratio_from_text(text):
    """Shares per ADS stated in a 20-F ("each ADS represents five (5) common shares"). Returns
    (ratio, evidence sentence, all candidates) or (None, None, {}) when the filing never states one."""
    votes, evidence = {}, {}
    for rx in _ADR_RES:
        for m in rx.finditer(text):
            v = _num(m)
            if not v or v <= 0 or v > 1000:
                continue
            v = round(v, 4)
            votes[v] = votes.get(v, 0) + 1
            evidence.setdefault(v, " ".join(text[max(0, m.start() - 40):m.end() + 10].split()))
    if not votes:
        return None, None, {}
    best = max(votes, key=lambda k: votes[k])
    return best, evidence[best], votes


def detect_adr(identity, dest, refresh=False):
    """For a 20-F filer, read the latest 20-F and record how many shares one ADS stands for. Writes
    dest/adr.json, which metrics.py uses for market cap and per-share multiples."""
    cik = identity["cik"]
    sub = read_json(os.path.join(dest, "sec", "submissions.json")) or cached_json(
        f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", os.path.join(dest, "sec", "submissions.json"),
        refresh=refresh)
    rec = sub["filings"]["recent"]
    rows = [dict(zip(rec.keys(), vals)) for vals in zip(*rec.values())]
    annual = [r for r in rows if r["form"] in ("10-K", "20-F", "40-F")][:1]
    out = {"form": annual[0]["form"] if annual else None, "ratio": None, "evidence": None, "source": None,
           "candidates": {}, "status": "not_20f"}
    if annual and annual[0]["form"] == "20-F":
        r = annual[0]
        txt = os.path.join(dest, "filings", f"20-F-{r['filingDate']}.txt")
        if not os.path.exists(txt):
            txt = os.path.join(dest, "sec", f"20-F-{r['filingDate']}.txt")
        try:
            text = download_doc(cik, r["accessionNumber"], r["primaryDocument"], txt, refresh)
        except Exception as e:
            out["status"] = f"could not read the 20-F: {e}"
            text = ""
        ratio, ev, votes = adr_ratio_from_text(text)
        out.update({"source": filing_doc_url(cik, r["accessionNumber"], r["primaryDocument"]),
                    "candidates": {str(k): v for k, v in votes.items()}})
        if ratio:
            out.update({"ratio": ratio, "evidence": ev, "status": "found"})
        elif text and not re.search(_ADS, text):
            out.update({"ratio": 1.0, "status": "no_ads", "evidence": "the 20-F never mentions ADSs, so the listed "
                        "shares are taken as ordinary shares"})
        elif text:
            out["status"] = "not_found"
    write_json(os.path.join(dest, "adr.json"), out)
    return out


def staleness_warnings(st, identity, dest, refresh=False):
    """XBRL companyfacts sometimes lags or skips a filing (TSMC's 2025 20-F is missing).
    Compare against the filing list so the data-room agent knows what to fill from text."""
    out = []
    try:
        sub = cached_json(f"https://data.sec.gov/submissions/CIK{int(identity['cik']):010d}.json",
                          os.path.join(dest, "sec", "submissions.json"), refresh=refresh)
        rec = sub["filings"]["recent"]
        last_end = st["annual"]["periods"][-1]["end"] if st["annual"]["periods"] else "0000"
        for form, date, period in zip(rec["form"], rec["filingDate"], rec["reportDate"]):
            if form in ("10-K", "20-F", "40-F") and period and period > last_end:
                out.append(f"{form} for period {period} (filed {date}) is not in XBRL companyfacts. "
                           f"Take that fiscal year from the filing text and record it with metrics.py add.")
                break
        q_end = st["ttm"].get("as_of") or last_end
        for form, date, period in zip(rec["form"], rec["filingDate"], rec["reportDate"]):
            if form == "10-Q" and period and period > q_end:
                out.append(f"10-Q for period {period} (filed {date}) is newer than the TTM data ({q_end}).")
                break
    except Exception as e:
        out.append(f"could not compare against the filing list: {e}")
    return out


# TTM items the metrics use; a lag in anything else (taxes paid, interest paid) is normal and not worth a warning
TTM_KEY_ITEMS = {"revenue", "cost_of_revenue", "gross_profit", "operating_income", "net_income", "pretax_income",
                 "income_tax", "interest_expense", "cfo", "capex", "sbc", "rnd", "sga", "dna", "depreciation",
                 "amort_intangibles"}


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--what", default="facts,filings,insiders")
    ap.add_argument("--cik", type=int, default=None, help="fetch for another company (peers)")
    ap.add_argument("--ticker", default=None)
    ap.add_argument("--dest", default=None)
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()

    paths = run_paths(args.run_dir)
    run = read_json(paths["run_json"], {})
    identity = dict(run.get("identity", {}))
    if args.cik:
        identity = {"cik": args.cik, "ticker": args.ticker}
    if not identity.get("cik"):
        sys.exit("No SEC CIK for this company. Use annual reports instead (see agents/data-room.md).")
    dest = os.path.abspath(args.dest or paths["data"])
    what = set(args.what.split(","))

    if "facts" in what:
        facts = cached_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(identity['cik']):010d}.json",
                            os.path.join(dest, "sec", "companyfacts.json"), refresh=args.refresh)
        st = build_statements(facts, identity)
        behind = {k: v for k, v in (st["ttm"].get("items_behind") or {}).items() if k in TTM_KEY_ITEMS}
        ttm_warn = ([f"TTM for {', '.join(sorted(behind))} stops earlier than {st['ttm']['as_of']} because the latest 10-Q "
                     f"does not tag it, so the TTM value is the last full year. Take it from the 10-Q and record it "
                     f"with metrics.py add if a slide depends on it."] if behind else [])
        st["warnings"] = (staleness_warnings(st, identity, dest, args.refresh) + st["latest_balance"].get("checks", [])
                          + ttm_warn)
        write_json(os.path.join(dest, "statements.json"), st)
        for w in st["warnings"]:
            log("WARNING:", w)
        labels = [p["label"] for p in st["annual"]["periods"]]
        log(f"statements.json: {len(labels)} fiscal years {labels[0] if labels else ''}..{labels[-1] if labels else ''}, "
            f"{st['meta']['taxonomy']} {st['meta']['currency']}, TTM as of {st['ttm'].get('as_of')}, "
            f"{len(st['gaps'])} items with gaps")
    if "filings" in what:
        idx = fetch_filings(identity, dest, refresh=args.refresh, as_of=run.get("as_of"))
        log(f"filings: {len(idx)} documents -> {os.path.join(dest, 'filings')}")
    if "facts" in what:
        a = detect_adr(identity, dest, refresh=args.refresh)
        if a["status"] == "found":
            log(f"ADR: one ADS = {a['ratio']:g} shares (from the 20-F: \"{a['evidence'][:140]}\")")
            if len(a["candidates"]) > 1:
                log(f"WARNING: the 20-F states more than one ADS ratio {a['candidates']}; check the cover page "
                    f"and pass --adr-ratio N if {a['ratio']:g} is wrong.")
        elif a["status"] == "not_found":
            log("WARNING: 20-F filer but no ADS ratio found in the filing text. Find it on the 20-F cover or the "
                "depositary's site and pass --adr-ratio N; until then market cap and per-share multiples assume 1.")
        elif a["status"].startswith("could not"):
            log("WARNING:", a["status"])
    if "insiders" in what:
        s = fetch_insiders(identity, dest, refresh=args.refresh, as_of=run.get("as_of"))
        log(f"insiders: {s['transactions']} transactions in {s['filings_read']} Form 4s; "
            f"buys {s['open_market_buys_total']:,.0f} sells {s['open_market_sells_total']:,.0f}")
    if not args.cik:
        update_run(args.run_dir, phases={"fetch_sec": "done"})


if __name__ == "__main__":
    main()
