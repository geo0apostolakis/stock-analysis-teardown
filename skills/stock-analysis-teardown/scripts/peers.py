#!/usr/bin/env python3
"""Build the peer comparison table and expose peer numbers as slide tokens.

usage:
  peers.py build RUN_DIR
  peers.py manual RUN_DIR TICKER --name "Alchip Technologies" --exchange TWSE --currency TWD \
          --set gross_margin=0.68 --set revenue_growth=2.05 --source S31 [--source-url URL]

Reads data/peers/<TICKER>/metrics.json for SEC-filing peers (built by collect.py) and
data/peers_manual.json for peers that do not file with the SEC (entered by the data-room agent,
each value with a source id). Writes data/peers.json and adds keys to the company's metrics.json:
  peer.<TICKER>.<metric>      e.g. peer.AVGO.gross_margin
  peer_median.<metric>        median across peers (company excluded)
Ticker and exchange for each peer are checked against SEC's list so a deck can't swap them.
"""
import argparse
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import display_name, locked, log, read_json, run_paths, update_run, write_json  # noqa: E402

# metric -> (metrics.json key, unit, label)
COLUMNS = [
    ("market_cap_usd", None, "money_m", "Market cap (USD)"),
    ("revenue_ttm", "revenue@TTM", "money_m", "Revenue, TTM"),
    ("revenue_growth", "revenue_growth@TTM", "pct", "Revenue growth, TTM vs prior TTM"),
    ("revenue_cagr", "revenue_cagr", "pct", "Revenue CAGR, last 4 fiscal years"),
    ("gross_margin", "gross_margin@TTM", "pct", "Gross margin, TTM"),
    ("operating_margin", "operating_margin@TTM", "pct", "Operating margin, TTM"),
    ("net_margin", "net_margin@TTM", "pct", "Net margin, TTM"),
    ("fcf_margin", "fcf_margin@TTM", "pct", "FCF margin, TTM"),
    ("roic", "roic@LASTFY", "pct", "ROIC, last fiscal year"),
    ("net_debt_to_ebitda", "net_debt_to_ebitda@LATEST", "x", "Net debt / EBITDA"),
    ("pe_ttm", "pe_ttm", "x", "P/E, TTM"),
    ("ev_ebitda_ttm", "ev_ebitda_ttm", "x", "EV/EBITDA, TTM"),
    ("ev_sales_ttm", "ev_sales_ttm", "x", "EV/Sales, TTM"),
    ("p_fcf_ttm", "p_fcf_ttm", "x", "Price/FCF, TTM"),
    ("fcf_yield", "fcf_yield_ttm", "pct", "FCF yield, TTM"),
    ("sbc_pct_revenue", "sbc_pct_revenue@LASTFY", "pct", "SBC as % of revenue, last fiscal year"),
]


def row_from_metrics(m, ticker):
    vals = m["values"]
    last = m["meta"]["display_periods"][-1] if m["meta"].get("display_periods") else None
    row = {"ticker": ticker, "name": display_name(m["meta"].get("name")), "legal_name": m["meta"].get("name"), "currency": m["meta"].get("currency"),
           "source": "SEC filings + Yahoo price; computed by metrics.py", "as_of": m["meta"].get("ttm_as_of")}
    for col, key, unit, _ in COLUMNS:
        if key is None:
            continue
        k = key.replace("@LASTFY", f"@{last}") if last else key
        v = vals.get(k)
        row[col] = v["v"] if v else None
    mc = vals.get("market_cap")
    if mc:
        ccy = mc.get("ccy") or m["meta"].get("currency")
        fx_to_usd = 1.0 if ccy == "USD" else None
        row["market_cap_usd"] = mc["v"] * fx_to_usd if fx_to_usd else None
        row["market_cap_local"] = mc["v"]
        row["market_cap_currency"] = ccy
    return row


def build(run_dir):
    paths = run_paths(run_dir)
    data = paths["data"]
    main = read_json(os.path.join(data, "metrics.json"))
    if not main:
        sys.exit("run metrics.py compute first")
    run = read_json(paths["run_json"], {})
    ticker = run.get("identity", {}).get("ticker")
    sec_list = read_json(os.path.join(os.path.expanduser("~"), ".cache", "stock-analysis-teardown",
                                      "company_tickers_exchange.json"), {}) or {}
    sec_map = {}
    if sec_list:
        f = sec_list["fields"]
        for r in sec_list["data"]:
            rec = dict(zip(f, r))
            sec_map[str(rec["ticker"]).upper()] = rec

    rows = [dict(row_from_metrics(main, ticker), is_subject=True)]
    peers_dir = os.path.join(data, "peers")
    checks = []
    for t in sorted(os.listdir(peers_dir)) if os.path.isdir(peers_dir) else []:
        m = read_json(os.path.join(peers_dir, t, "metrics.json"))
        if not m:
            continue
        r = row_from_metrics(m, t)
        sec = sec_map.get(t.upper())
        if sec:
            r["exchange"] = sec.get("exchange")
            r["sec_name"] = sec.get("name")
            checks.append(f"{t}: SEC lists '{sec.get('name')}' on {sec.get('exchange')}")
        rows.append(r)
    manual = read_json(os.path.join(data, "peers_manual.json"), {}) or {}
    for t, e in manual.items():
        r = {"ticker": t, "name": e.get("name"), "exchange": e.get("exchange"), "currency": e.get("currency"),
             "source": e.get("source"), "source_url": e.get("source_url"), "manual": True}
        for col, _, _, _ in COLUMNS:
            r[col] = e.get("values", {}).get(col)
        if t.upper() in sec_map and sec_map[t.upper()].get("name", "").lower()[:6] != (e.get("name") or "").lower()[:6]:
            checks.append(f"WARNING {t}: SEC says this ticker is '{sec_map[t.upper()]['name']}', manual entry says '{e.get('name')}'")
        rows.append(r)

    # medians across peers (subject excluded)
    med = {}
    base_ccy = rows[0].get("currency")
    for col, _, unit, label in COLUMNS:
        # money in different currencies cannot share a median (Alchip reports in TWD); ratios can
        same_ccy = unit != "money_m" or col == "market_cap_usd"
        xs = [r[col] for r in rows[1:] if isinstance(r.get(col), (int, float))
              and (same_ccy or r.get("currency") == base_ccy)]
        if xs:
            med[col] = statistics.median(xs)
    high_roic = sorted(r["ticker"] for r in rows if isinstance(r.get("roic"), (int, float)) and r["roic"] > 1.0)
    if high_roic:
        checks.append(f"ROIC is above 100% for {', '.join(high_roic)}. Invested capital is tiny next to profit (net "
                      f"cash, little equity), so ROIC does not compare with the others. Say so on any slide that shows it.")
    other = sorted(r["ticker"] for r in rows[1:] if r.get("currency") and r.get("currency") != base_ccy)
    if other:
        checks.append(f"{', '.join(other)} {'reports' if len(other) == 1 else 'report'} in another currency, so "
                      f"{'it is' if len(other) == 1 else 'they are'} left out of the revenue median "
                      f"(ratios and the USD market cap still count)")
    out = {"columns": [{"key": c, "unit": u, "label": lbl} for c, _, u, lbl in COLUMNS], "rows": rows,
           "medians": med, "checks": checks}
    write_json(os.path.join(data, "peers.json"), out)

    # expose as tokens in the company's metrics.json
    V = main["values"]
    for k in [k for k in V if k.startswith("peer.") or k.startswith("peer_median.")]:
        del V[k]
    units = {c: u for c, _, u, _ in COLUMNS}
    labels = {c: lbl for c, _, _, lbl in COLUMNS}
    for r in rows[1:]:
        for c in units:
            if isinstance(r.get(c), (int, float)):
                ccy = "USD" if c == "market_cap_usd" else (r.get("currency") if units[c] == "money_m" else None)
                V[f"peer.{r['ticker']}.{c}"] = {"v": r[c], "unit": units[c], "label": f"{r.get('name') or r['ticker']}: {labels[c]}",
                                                **({"ccy": ccy} if ccy else {}),
                                                **({"source": r.get("source")} if r.get("manual") else {})}
    for c, v in med.items():
        V[f"peer_median.{c}"] = {"v": v, "unit": units[c], "label": f"Peer median: {labels[c]}",
                                 **({"ccy": "USD"} if c == "market_cap_usd" else {})}
    write_json(os.path.join(data, "metrics.json"), main)
    update_run(run_dir, phases={"peers": "done"})
    log(f"peers.json: {len(rows) - 1} peers; checks: {checks}")


def manual(args):
    paths = run_paths(args.run_dir)
    path = os.path.join(paths["data"], "peers_manual.json")
    data = read_json(path, {}) or {}
    e = data.get(args.ticker, {"values": {}})
    e.update({"name": args.name or e.get("name"), "exchange": args.exchange or e.get("exchange"),
              "currency": args.currency or e.get("currency"), "source": args.source or e.get("source"),
              "source_url": args.source_url or e.get("source_url")})
    for kv in args.set or []:
        k, _, v = kv.partition("=")
        e["values"][k.strip()] = float(v)
    data[args.ticker] = e
    write_json(path, data)
    print(f"saved manual peer {args.ticker}: {e}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("run_dir")
    m = sub.add_parser("manual"); m.add_argument("run_dir"); m.add_argument("ticker")
    m.add_argument("--name"); m.add_argument("--exchange"); m.add_argument("--currency")
    m.add_argument("--set", action="append"); m.add_argument("--source"); m.add_argument("--source-url")
    args = ap.parse_args()
    if args.cmd == "build":
        with locked(os.path.join(run_paths(args.run_dir)["data"], "metrics.json")):
            build(args.run_dir)
    else:
        with locked(os.path.join(run_paths(args.run_dir)["data"], "metrics.json")):
            manual(args)
            build(args.run_dir)   # refresh peers.json and the peer tokens straight away


if __name__ == "__main__":
    main()
