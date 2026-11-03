#!/usr/bin/env python3
"""Step 0. Turn a ticker into a company identity and create (or resume) the run folder.

usage: resolve.py TICKER [--out-root DIR] [--date YYYY-MM-DD]

Prints the run folder path on the last line of stdout. Writes run.json with the
identity: SEC CIK, legal name, exchange, fiscal year end, SIC industry, filer type,
and the Yahoo symbol used for prices. If the ticker is not an SEC filer, the run
is marked sec_filer=false and the data-room agent works from annual reports.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (cached_json, display_name, get_json, log, read_json, run_paths, today,  # noqa: E402
                     update_run, write_json)

SEC_TICKERS = "https://www.sec.gov/files/company_tickers_exchange.json"
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "stock-analysis-teardown")


def default_out_root():
    return os.environ.get("TEARDOWN_OUTPUT_DIR") or os.path.join(os.getcwd(), "teardowns")


def sec_lookup(ticker):
    data = cached_json(SEC_TICKERS, os.path.join(CACHE, "company_tickers_exchange.json"),
                       refresh=_stale(os.path.join(CACHE, "company_tickers_exchange.json")))
    fields = data["fields"]
    want = {ticker.upper(), ticker.upper().replace(".", "-"), ticker.upper().replace("-", ".")}
    for row in data["data"]:
        rec = dict(zip(fields, row))
        if str(rec.get("ticker", "")).upper() in want:
            return rec
    return None


def _stale(path, days=7):
    import time
    return (not os.path.exists(path)) or (time.time() - os.path.getmtime(path) > days * 86400)


def yahoo_search(query):
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}&quotesCount=5&newsCount=0"
        res = get_json(url)
        return res.get("quotes", [])
    except Exception as e:  # pragma: no cover
        log("yahoo search failed:", e)
        return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ticker")
    ap.add_argument("--out-root", default=None)
    ap.add_argument("--date", default=today())
    args = ap.parse_args()

    ticker = args.ticker.strip().upper()
    out_root = os.path.abspath(args.out_root or default_out_root())
    run_dir = os.path.join(out_root, f"{ticker.replace('/', '-')}-{args.date}")
    paths = run_paths(run_dir)
    for key in ("data", "notes", "parts", "build"):
        os.makedirs(paths[key], exist_ok=True)

    existing = read_json(paths["run_json"])
    if existing and existing.get("identity"):
        log(f"Resuming existing run. Phases done: {existing.get('phases', {})}")
        print(run_dir)
        return

    identity = {"ticker": ticker, "sec_filer": False}
    rec = sec_lookup(ticker)
    if rec:
        cik = int(rec["cik"])
        sub = cached_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json",
                          os.path.join(paths["data"], "sec", "submissions.json"))
        forms = set(sub.get("filings", {}).get("recent", {}).get("form", []))
        annual_form = next((f for f in ("10-K", "20-F", "40-F") if f in forms), None)
        fye = sub.get("fiscalYearEnd") or ""
        identity.update({
            "sec_filer": True,
            "cik": cik,
            "name": sub.get("name") or rec.get("name"),
            "exchange": rec.get("exchange") or (sub.get("exchanges") or [None])[0],
            "tickers": sub.get("tickers"),
            "fiscal_year_end_mmdd": fye,
            "fiscal_year_end_month": int(fye[:2]) if len(fye) == 4 else None,
            "sic": sub.get("sic"),
            "sic_description": sub.get("sicDescription"),
            "state_of_incorporation": sub.get("stateOfIncorporation"),
            "category": sub.get("category"),
            "annual_form": annual_form,
            "foreign_private_issuer": annual_form in ("20-F", "40-F"),
            "website": sub.get("website") or None,
            "yahoo_symbol": ticker.replace(".", "-"),
        })
    else:
        quotes = yahoo_search(ticker)
        q = next((q for q in quotes if q.get("symbol", "").upper() == ticker), quotes[0] if quotes else None)
        if q:
            identity.update({
                "name": q.get("longname") or q.get("shortname"),
                "exchange": q.get("exchDisp") or q.get("exchange"),
                "yahoo_symbol": q.get("symbol"),
                "quote_type": q.get("quoteType"),
                "industry": q.get("industry"),
                "sector": q.get("sector"),
            })
            log("Not an SEC filer. Financials must come from annual reports (data confidence: lower).")
        else:
            log(f"Could not resolve ticker {ticker} on SEC or Yahoo.")
            identity["unresolved"] = True

    if identity.get("name"):
        identity["display_name"] = display_name(identity["name"])
    update_run(run_dir, identity=identity, created=today(), as_of=args.date,
               phases={"resolve": "done"}, path=run_dir)
    write_json(os.path.join(paths["data"], "identity.json"), identity)
    log(f"{identity.get('name')} | {identity.get('exchange')} | CIK {identity.get('cik')} | FYE {identity.get('fiscal_year_end_mmdd')}")
    print(run_dir)


if __name__ == "__main__":
    main()
