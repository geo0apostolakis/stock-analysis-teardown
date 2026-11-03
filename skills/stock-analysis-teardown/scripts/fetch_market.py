#!/usr/bin/env python3
"""Market data from Yahoo Finance's public chart endpoint (no key).

usage:
  fetch_market.py RUN_DIR                         company in run.json -> RUN_DIR/data/market.json
  fetch_market.py RUN_DIR --symbol AVGO --dest RUN_DIR/data/peers/AVGO

Writes market.json with:
  price, currency, exchange, price time, 52-week range
  5 years of daily closes (for the price chart and historical multiples)
  stock splits and dividends (splits are used to put old per-share data on today's share basis)
  beta against SPY from 5 years of weekly returns, 1/3/5-year returns, max drawdown, volatility
  10-year US Treasury yield (risk-free rate for the cost of capital)
  FX rate to USD when the listing currency differs from the reporting currency
"""
import argparse
import datetime as dt
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import get_json, log, read_json, run_paths, update_run, write_json  # noqa: E402

CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range={rng}&interval={iv}&events=div%7Csplit&includeAdjustedClose=true"


def chart(sym, rng="5y", iv="1d"):
    res = get_json(CHART.format(sym=sym, rng=rng, iv=iv))
    r = res["chart"]["result"][0]
    meta = r["meta"]
    ts = r.get("timestamp") or []
    q = r["indicators"]["quote"][0]
    adj = (r["indicators"].get("adjclose") or [{}])[0].get("adjclose") or q.get("close")
    rows = []
    for i, t in enumerate(ts):
        c = q["close"][i]
        if c is None:
            continue
        rows.append({"date": dt.datetime.utcfromtimestamp(t).date().isoformat(), "close": round(c, 4),
                     "adj": round(adj[i], 4) if adj and adj[i] is not None else round(c, 4)})
    ev = r.get("events", {})
    splits = [{"date": dt.datetime.utcfromtimestamp(int(k)).date().isoformat(),
               "ratio": v["numerator"] / v["denominator"], "text": v.get("splitRatio")}
              for k, v in (ev.get("splits") or {}).items()]
    divs = [{"date": dt.datetime.utcfromtimestamp(int(k)).date().isoformat(), "amount": v["amount"]}
            for k, v in (ev.get("dividends") or {}).items()]
    return meta, rows, sorted(splits, key=lambda s: s["date"]), sorted(divs, key=lambda d: d["date"])


def weekly(rows):
    out, last_week = [], None
    for r in rows:
        d = dt.date.fromisoformat(r["date"])
        wk = d.isocalendar()[:2]
        if wk != last_week:
            out.append(r)
            last_week = wk
        else:
            out[-1] = r
    return out


def returns(series):
    return [(b / a - 1.0) for a, b in zip(series, series[1:]) if a]


def beta_vs(stock_rows, bench_rows):
    s = {r["date"]: r["adj"] for r in weekly(stock_rows)}
    b = {r["date"]: r["adj"] for r in weekly(bench_rows)}
    dates = sorted(set(s) & set(b))
    if len(dates) < 52:
        return None, len(dates)
    rs, rb = returns([s[d] for d in dates]), returns([b[d] for d in dates])
    mb = sum(rb) / len(rb)
    ms = sum(rs) / len(rs)
    cov = sum((x - ms) * (y - mb) for x, y in zip(rs, rb)) / (len(rb) - 1)
    var = sum((y - mb) ** 2 for y in rb) / (len(rb) - 1)
    return (cov / var if var else None), len(rs)


def total_return(rows, days):
    if not rows:
        return None
    end = dt.date.fromisoformat(rows[-1]["date"])
    target = end - dt.timedelta(days=days)
    past = [r for r in rows if dt.date.fromisoformat(r["date"]) <= target]
    if not past:
        return None
    return rows[-1]["adj"] / past[-1]["adj"] - 1.0


def max_drawdown(rows):
    peak, mdd, peak_date, trough_date = -1, 0.0, None, None
    cur_peak_date = None
    for r in rows:
        if r["adj"] > peak:
            peak, cur_peak_date = r["adj"], r["date"]
        dd = r["adj"] / peak - 1.0
        if dd < mdd:
            mdd, peak_date, trough_date = dd, cur_peak_date, r["date"]
    return {"max_drawdown": mdd, "peak_date": peak_date, "trough_date": trough_date}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--symbol", default=None)
    ap.add_argument("--dest", default=None)
    ap.add_argument("--benchmark", default="SPY")
    args = ap.parse_args()

    paths = run_paths(args.run_dir)
    run = read_json(paths["run_json"], {})
    ident = run.get("identity", {})
    sym = args.symbol or ident.get("yahoo_symbol") or ident.get("ticker")
    dest = os.path.abspath(args.dest or paths["data"])

    meta, rows, splits, divs = chart(sym)
    try:  # full split history, so 10-year per-share data can be put on today's share basis
        _, _, all_splits, _ = chart(sym, "max", "1mo")
        splits = all_splits or splits
    except Exception as e:
        log("split history lookup failed:", e)
    price = meta.get("regularMarketPrice")
    price_time = dt.datetime.utcfromtimestamp(meta.get("regularMarketTime", 0)).isoformat() + "Z"
    currency = meta.get("currency")
    last_year = [r for r in rows if dt.date.fromisoformat(r["date"]) >= dt.date.fromisoformat(rows[-1]["date"]) - dt.timedelta(days=365)] if rows else []

    out = {
        "symbol": sym, "price": price, "price_time": price_time, "currency": currency,
        "exchange": meta.get("fullExchangeName") or meta.get("exchangeName"),
        "instrument": meta.get("instrumentType"),
        "high_52w": max((r["close"] for r in last_year), default=None),
        "low_52w": min((r["close"] for r in last_year), default=None),
        "splits": splits, "dividends": divs,
        "trailing_dividends_12m": round(sum(d["amount"] for d in divs if d["date"] >= (dt.date.today() - dt.timedelta(days=365)).isoformat()), 4),
        "returns": {"1y": total_return(rows, 365), "3y": total_return(rows, 3 * 365), "5y": total_return(rows, 5 * 365 - 5)},
        "drawdown_5y": max_drawdown(rows),
        "history": rows,
        "source": "Yahoo Finance chart API",
        "source_url": f"https://finance.yahoo.com/quote/{sym}/history",
    }
    if len(rows) > 30:
        daily = returns([r["adj"] for r in rows[-252:]])
        mean = sum(daily) / len(daily)
        out["volatility_1y"] = math.sqrt(sum((x - mean) ** 2 for x in daily) / (len(daily) - 1)) * math.sqrt(252)

    if not args.symbol or args.symbol == ident.get("yahoo_symbol"):
        try:
            _, bench, _, _ = chart(args.benchmark)
            b, n = beta_vs(rows, bench)
            out["beta"] = {"value": b, "benchmark": args.benchmark, "method": f"{n} weekly returns, up to 5 years"}
            out["benchmark_returns"] = {"1y": total_return(bench, 365), "3y": total_return(bench, 3 * 365),
                                        "5y": total_return(bench, 5 * 365 - 5)}
            out["benchmark_history"] = [{"date": r["date"], "adj": r["adj"]} for r in weekly(bench)]
        except Exception as e:
            log("benchmark failed:", e)
        try:
            tnx, _, _, _ = chart("^TNX", "5d")
            out["risk_free"] = {"value": tnx["regularMarketPrice"] / 100.0, "instrument": "US 10-year Treasury yield (^TNX)",
                                "date": dt.datetime.utcfromtimestamp(tnx.get("regularMarketTime", 0)).date().isoformat()}
        except Exception as e:
            log("risk-free fetch failed:", e)

    st = read_json(os.path.join(dest, "statements.json"))
    rep_ccy = (st or {}).get("meta", {}).get("currency")
    if rep_ccy and currency and rep_ccy != currency:
        try:
            fx, _, _, _ = chart(f"{rep_ccy}{currency}=X", "5d")
            out["fx"] = {"pair": f"{rep_ccy}{currency}", "rate": fx["regularMarketPrice"],
                         "note": f"multiply {rep_ccy} figures by this rate to compare with the {currency} price"}
        except Exception as e:
            log("fx fetch failed:", e)
            out["fx"] = {"pair": f"{rep_ccy}{currency}", "rate": None, "note": "FX lookup failed; set it manually"}

    write_json(os.path.join(dest, "market.json"), out)
    log(f"{sym}: {currency} {price} at {price_time}; {len(rows)} daily closes; splits {[(s['date'], s['text']) for s in splits]}"
        f"; beta {out.get('beta', {}).get('value')}; rf {out.get('risk_free', {}).get('value')}")
    if not args.symbol:
        update_run(args.run_dir, phases={"fetch_market": "done"})


if __name__ == "__main__":
    main()
