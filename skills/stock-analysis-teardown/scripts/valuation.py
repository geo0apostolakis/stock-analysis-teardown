#!/usr/bin/env python3
"""Part 4 valuation: cost of capital, bull/base/bear DCF, reverse DCF, sensitivity, football field.

usage:
  valuation.py init RUN_DIR     write data/valuation_inputs.json pre-filled from metrics (the agent edits it)
  valuation.py run  RUN_DIR     compute data/valuation.json and add valuation tokens to metrics.json

Cash flow definition. The DCF discounts owner free cash flow = operating cash flow - capex -
stock-based compensation. SBC is treated as a real cost because it is paid in shares.
Scenario inputs are yearly revenue growth and owner-FCF margin paths (10 years; a shorter
list repeats its last value). Discounting is end of year. Terminal value is Gordon growth.

Cost of equity = risk-free + adjusted beta x equity risk premium.
Adjusted beta = 0.67 x raw beta + 0.33 (Blume), raw beta from fetch_market.py.
Cost of debt = last fiscal year interest expense / average total debt, kept between
risk-free and risk-free + 6%. Weights use market cap and latest total debt.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import locked, log, read_json, run_paths, update_run, write_json  # noqa: E402

YEARS = 10


def V(m, key):
    v = m["values"].get(key)
    return v["v"] if v else None


def path(lst, n=YEARS):
    lst = list(lst or [])
    if not lst:
        return [0.0] * n
    return (lst + [lst[-1]] * n)[:n]


def fade(start, end, n=YEARS):
    return [start + (end - start) * i / (n - 1) for i in range(n)]


def init(run_dir):
    p = run_paths(run_dir)
    m = read_json(os.path.join(p["data"], "metrics.json"))
    last = m["meta"]["display_periods"][-1]
    g_ttm = V(m, "revenue_growth@TTM") or V(m, f"revenue_growth@{last}") or 0.08
    g0 = max(min(g_ttm, 0.40), -0.10)
    hist_margins = [v for k, v in ((k, x["v"]) for k, x in m["values"].items() if k.startswith("fcf_less_sbc_margin@FY"))]
    m_now = (V(m, "fcf@TTM") - (V(m, "sbc@TTM") or 0)) / V(m, "revenue@TTM") if V(m, "fcf@TTM") and V(m, "revenue@TTM") else (hist_margins[-1] if hist_margins else 0.10)
    m_best = max(hist_margins) if hist_margins else m_now
    tg = 0.03
    inputs = {
        "_read_me": "Edit every number and write the reason next to it. Growth and margins are fractions. "
                    "Margins are owner FCF (CFO - capex - SBC) / revenue. Lists cover years 1-10; a short list repeats its last value.",
        "erp": 0.05, "erp_reason": "Long-run US equity risk premium assumption (Damodaran's implied ERP has ranged roughly 4-6%).",
        "beta_override": None, "beta_reason": "Leave null to use the adjusted 5-year weekly beta.",
        "extra_shares_m": 0, "extra_shares_reason": "Millions of shares to count on top of common, such as convertible "
                         "preferred as converted. Per-share values, market cap and the reverse DCF all use this basis.",
        "eps_key": "eps@TTM", "eps_key_reason": "EPS behind the peer P/E bar. If the TTM holds a one-off gain or loss, "
                  "record a clean EPS with metrics.py add and put its key here.",
        "terminal_growth": tg, "terminal_growth_reason": "Long-run nominal growth near GDP.",
        "tax_rate": 0.21,
        "scenarios": {
            "bear": {"probability": 0.25, "revenue_growth": [round(x, 4) for x in fade(g0 * 0.4, tg)],
                     "fcf_margin": [round(x, 4) for x in fade(m_now, m_now * 0.8)],
                     "narrative": "TODO: what has to go wrong"},
            "base": {"probability": 0.5, "revenue_growth": [round(x, 4) for x in fade(g0 * 0.8, tg)],
                     "fcf_margin": [round(x, 4) for x in fade(m_now, max(m_now, (m_now + m_best) / 2))],
                     "narrative": "TODO: the central case and why"},
            "bull": {"probability": 0.25, "revenue_growth": [round(x, 4) for x in fade(g0 * 1.1, tg + 0.01)],
                     "fcf_margin": [round(x, 4) for x in fade(m_now, max(m_best, m_now) * 1.15)],
                     "narrative": "TODO: what has to go right"},
        },
        "reverse_dcf": {"terminal_fcf_margin": round(max(m_best, m_now), 4),
                        "reason": "Margin the business could plausibly reach at maturity (used when TTM owner FCF is too small)."},
        "analyst_targets": {"low": None, "mean": None, "high": None, "count": None, "source": None, "date": None},
        "exclude_from_football_field": [],
    }
    out = os.path.join(p["data"], "valuation_inputs.json")
    if os.path.exists(out):
        log(f"{out} already exists; not overwriting")
    else:
        write_json(out, inputs)
        log(f"wrote {out}")
    print(out)


def dcf(rev0, growth, margin, wacc, g, years=YEARS):
    rev, pv, rows = rev0, 0.0, []
    for t in range(1, years + 1):
        rev = rev * (1 + growth[t - 1])
        fcf = rev * margin[t - 1]
        disc = (1 + wacc) ** t
        pv += fcf / disc
        rows.append({"year": t, "revenue": rev, "fcf": fcf, "pv": fcf / disc})
    tv = rows[-1]["fcf"] * (1 + g) / (wacc - g)
    pv_tv = tv / (1 + wacc) ** years
    return pv + pv_tv, rows, pv_tv


def solve(fn, target, lo, hi, iters=200):
    flo, fhi = fn(lo) - target, fn(hi) - target
    if flo * fhi > 0:
        return None
    for _ in range(iters):
        mid = (lo + hi) / 2
        fm = fn(mid) - target
        if abs(fm) < 1e-6 * max(1.0, abs(target)):
            return mid
        if flo * fm <= 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    return (lo + hi) / 2


def run(run_dir):
    p = run_paths(run_dir)
    data = p["data"]
    m = read_json(os.path.join(data, "metrics.json"))
    inp = read_json(os.path.join(data, "valuation_inputs.json"))
    if not inp:
        sys.exit("run valuation.py init first and edit data/valuation_inputs.json")
    meta = m["meta"]
    last = meta["display_periods"][-1]
    fx = meta.get("fx_reporting_to_price") or 1.0
    adr = meta.get("adr_ratio") or 1.0

    rf = V(m, "risk_free_rate") or 0.045
    raw_beta = V(m, "beta")
    beta = inp.get("beta_override") or (0.67 * raw_beta + 0.33 if raw_beta is not None else 1.0)
    erp = inp.get("erp", 0.05)
    ke = rf + beta * erp
    debt = V(m, "total_debt@LATEST") or 0.0
    cash = V(m, "cash_and_investments@LATEST") or 0.0
    mcap = V(m, "market_cap_reporting")
    ie = V(m, f"interest_expense@{last}")
    prev = meta["display_periods"][-2] if len(meta["display_periods"]) > 1 else last
    avg_debt = ((V(m, f"total_debt@{last}") or 0) + (V(m, f"total_debt@{prev}") or 0)) / 2
    kd = (ie / avg_debt) if ie and avg_debt else rf + 0.015
    kd = min(max(kd, rf), rf + 0.06)
    t = inp.get("tax_rate", 0.21)
    # convertible preferred, or other shares that convert at no cost, counted as common (millions of shares)
    extra = float(inp.get("extra_shares_m") or 0.0)
    px_rep = (V(m, "price") or 0.0) / ((fx or 1.0) * (adr or 1.0))
    if extra and mcap:
        mcap = mcap + extra * px_rep
    E, D = (mcap or 0.0), debt
    wacc = (E / (E + D)) * ke + (D / (E + D)) * kd * (1 - t) if (E + D) > 0 else ke
    g = inp.get("terminal_growth", 0.03)
    if wacc <= g + 0.01:
        log(f"WACC {wacc:.3f} is too close to terminal growth {g}; raising WACC floor to g + 2%")
        wacc = g + 0.02
    shares = (V(m, "shares_outstanding@LATEST") or 0.0) + extra or None
    rev0 = V(m, "revenue@TTM") or V(m, f"revenue@{last}")
    net_debt = debt - cash
    price = V(m, "price")
    ev_now = V(m, "enterprise_value")
    if ev_now and extra:
        ev_now = ev_now + extra * px_rep   # same share basis as the per-share values

    def per_share(ev):
        return (ev - net_debt) / shares * fx * adr if shares else None

    scen_out = {}
    for name, sc in inp["scenarios"].items():
        gr, mg = path(sc["revenue_growth"]), path(sc["fcf_margin"])
        ev, rows, pv_tv = dcf(rev0, gr, mg, wacc, g)
        ps = per_share(ev)
        scen_out[name] = {"probability": sc.get("probability"), "narrative": sc.get("narrative"), "ev": ev,
                          "equity_value": ev - net_debt, "per_share": ps,
                          "upside": (ps / price - 1) if ps and price else None,
                          "terminal_value_share_of_ev": pv_tv / ev if ev else None,
                          "revenue_cagr_10y": (rows[-1]["revenue"] / rev0) ** (1 / YEARS) - 1,
                          "year10_revenue": rows[-1]["revenue"], "year10_fcf_margin": mg[-1], "projection": rows,
                          "inputs": {"revenue_growth": gr, "fcf_margin": mg}}
    probs = [s["probability"] or 0 for s in scen_out.values()]
    weighted = sum((s["probability"] or 0) * (s["per_share"] or 0) for s in scen_out.values()) / sum(probs) if sum(probs) else None

    # sensitivity on the base case
    sens = None
    if "base" in inp["scenarios"]:
        b = inp["scenarios"]["base"]
        ws = [round(wacc + d, 4) for d in (-0.01, -0.005, 0, 0.005, 0.01)]
        gs = [round(g + d, 4) for d in (-0.01, -0.005, 0, 0.005, 0.01)]
        grid = []
        for w in ws:
            row = []
            for gg in gs:
                if w <= gg + 0.005:
                    row.append(None)
                else:
                    ev, _, _ = dcf(rev0, path(b["revenue_growth"]), path(b["fcf_margin"]), w, gg)
                    row.append(per_share(ev))
            grid.append(row)
        sens = {"wacc": ws, "terminal_growth": gs, "per_share": grid}

    # reverse DCF: what does today's enterprise value assume?
    rev_out = {}
    fcf_ttm = V(m, "fcf@TTM")
    sbc_ttm = V(m, "sbc@TTM") or 0.0
    owner = (fcf_ttm - sbc_ttm) if fcf_ttm is not None else None
    if ev_now and owner and owner > 0:
        def ev_for_growth(x):
            v, fcf = 0.0, owner
            for yr in range(1, YEARS + 1):
                fcf *= (1 + x)
                v += fcf / (1 + wacc) ** yr
            return v + fcf * (1 + g) / (wacc - g) / (1 + wacc) ** YEARS
        x = solve(ev_for_growth, ev_now, -0.5, 1.5)
        rev_out["implied_owner_fcf_cagr"] = x
        rev_out["owner_fcf_ttm"] = owner
    tm = (inp.get("reverse_dcf") or {}).get("terminal_fcf_margin")
    if ev_now and tm and rev0:
        m0 = owner / rev0 if owner is not None else tm
        def ev_for_rev_growth(x):
            ev, _, _ = dcf(rev0, [x] * YEARS, fade(m0, tm), wacc, g)
            return ev
        x = solve(ev_for_rev_growth, ev_now, -0.3, 1.5)
        rev_out["implied_revenue_cagr"] = x
        rev_out["terminal_fcf_margin"] = tm
        rev_out["implied_year10_revenue"] = rev0 * (1 + x) ** YEARS if x is not None else None
    hist_cagr = V(m, "revenue_cagr")
    rev_out["historical_revenue_cagr"] = hist_cagr

    # football field (price currency, per share)
    ff = []
    if V(m, "low_52w") and V(m, "high_52w"):
        ff.append({"label": "52-week range", "low": V(m, "low_52w"), "high": V(m, "high_52w"), "kind": "market"})
    if all(s in scen_out for s in ("bear", "bull")):
        ff.append({"label": "DCF bear to bull", "low": scen_out["bear"]["per_share"], "high": scen_out["bull"]["per_share"],
                   "mid": scen_out.get("base", {}).get("per_share"), "kind": "dcf"})
    peers = read_json(os.path.join(data, "peers.json"), {}) or {}
    prow = [r for r in peers.get("rows", [])[1:]]
    eps_key = inp.get("eps_key") or "eps@TTM"
    ebitda, eps, rev_ttm = V(m, "ebitda@TTM"), V(m, eps_key), V(m, "revenue@TTM")

    def rng(col):
        xs = [r[col] for r in prow if isinstance(r.get(col), (int, float)) and r[col] > 0]
        return (min(xs), max(xs)) if xs else None
    r = rng("ev_ebitda_ttm")
    if r and ebitda and ebitda > 0:
        ff.append({"label": f"Peer EV/EBITDA {r[0]:.0f}x to {r[1]:.0f}x", "low": per_share(r[0] * ebitda),
                   "high": per_share(r[1] * ebitda), "kind": "peers"})
    r = rng("ev_sales_ttm")
    if r and rev_ttm:
        ff.append({"label": f"Peer EV/Sales {r[0]:.1f}x to {r[1]:.1f}x", "low": per_share(r[0] * rev_ttm),
                   "high": per_share(r[1] * rev_ttm), "kind": "peers"})
    r = rng("pe_ttm")
    if r and eps and eps > 0:
        basis = "" if eps_key == "eps@TTM" else f" on {m['values'][eps_key].get('label', eps_key)}"
        ff.append({"label": f"Peer P/E {r[0]:.0f}x to {r[1]:.0f}x{basis}", "low": r[0] * eps * fx * adr,
                   "high": r[1] * eps * fx * adr, "kind": "peers"})
    hist = [x["v"] for k, x in m["values"].items() if k.startswith("ev_sales_hist@")]
    if len(hist) >= 3 and rev_ttm:
        ff.append({"label": f"Own EV/Sales history {min(hist):.1f}x to {max(hist):.1f}x",
                   "low": per_share(min(hist) * rev_ttm), "high": per_share(max(hist) * rev_ttm), "kind": "history"})
    at = inp.get("analyst_targets") or {}
    if at.get("low") and at.get("high"):
        ff.append({"label": "Analyst price targets", "low": at["low"], "high": at["high"], "mid": at.get("mean"),
                   "kind": "analysts", "source": at.get("source")})
    ff = [b for b in ff if b["label"] not in set(inp.get("exclude_from_football_field") or [])]

    out = {
        "as_of": meta.get("price_time"), "price": price, "price_currency": meta.get("price_currency"),
        "wacc": {"value": wacc, "cost_of_equity": ke, "cost_of_debt_pre_tax": kd, "risk_free": rf, "beta_raw": raw_beta,
                 "beta_used": beta, "erp": erp, "tax_rate": t, "equity_weight": E / (E + D) if E + D else None},
        "terminal_growth": g, "start_revenue": rev0, "net_debt": net_debt, "shares": shares,
        "scenarios": scen_out, "probability_weighted_per_share": weighted,
        "probability_weighted_upside": (weighted / price - 1) if weighted and price else None,
        "sensitivity": sens, "reverse_dcf": rev_out, "football_field": ff,
        "method": "Owner FCF (CFO - capex - SBC) DCF, 10 years, end-of-year discounting, Gordon terminal value.",
    }
    write_json(os.path.join(data, "valuation.json"), out)

    Vv = m["values"]
    def put(k, v, unit, label, ccy=None):
        if v is not None:
            Vv[k] = {"v": v, "unit": unit, "label": label, **({"ccy": ccy} if ccy else {})}
    pc = meta.get("price_currency") if meta.get("price_currency") != meta.get("currency") else None
    put("wacc", wacc, "pct", "Weighted average cost of capital")
    put("cost_of_equity", ke, "pct", "Cost of equity (CAPM)")
    put("cost_of_debt", kd, "pct", "Pre-tax cost of debt")
    if raw_beta is not None:
        put("beta_adjusted", 0.67 * raw_beta + 0.33, "ratio", "Adjusted beta (Blume: 0.67 x raw + 0.33)")
    put("beta_used", beta, "ratio", "Beta used in cost of equity" + (" (override)" if inp.get("beta_override") else ""))
    put("erp", erp, "pct", "Equity risk premium assumption")
    put("terminal_growth", g, "pct", "Terminal growth rate")
    for n, s in scen_out.items():
        put(f"dcf_{n}_per_share", s["per_share"], "ps", f"DCF value per share, {n} case", pc)
        put(f"dcf_{n}_upside", s["upside"], "pct", f"DCF {n} case vs current price")
        put(f"dcf_{n}_revenue_cagr", s["revenue_cagr_10y"], "pct", f"10-year revenue CAGR assumed, {n} case")
        put(f"dcf_{n}_fcf_margin_y10", s["year10_fcf_margin"], "pct", f"Year-10 owner FCF margin assumed, {n} case")
        put(f"dcf_{n}_tv_share", s["terminal_value_share_of_ev"], "pct", f"Terminal value share of EV, {n} case")
    put("dcf_weighted_per_share", weighted, "ps", "Probability-weighted DCF value per share", pc)
    put("dcf_weighted_upside", out["probability_weighted_upside"], "pct", "Probability-weighted value vs current price")
    put("reverse_dcf_owner_fcf_cagr", rev_out.get("implied_owner_fcf_cagr"), "pct",
        "Owner FCF growth for 10 years implied by today's enterprise value")
    put("reverse_dcf_revenue_cagr", rev_out.get("implied_revenue_cagr"), "pct",
        "Revenue growth for 10 years implied by today's enterprise value")
    put("reverse_dcf_terminal_margin", rev_out.get("terminal_fcf_margin"), "pct", "Terminal owner FCF margin used in the reverse DCF")
    put("owner_fcf@TTM", owner, "money_m", "Owner FCF, TTM (CFO - capex - SBC)")
    write_json(os.path.join(data, "metrics.json"), m)
    update_run(run_dir, phases={"valuation_model": "done"})
    log(json.dumps({"wacc": round(wacc, 4), "ke": round(ke, 4), "beta": round(beta, 2),
                    "per_share": {n: round(s["per_share"], 2) if s["per_share"] else None for n, s in scen_out.items()},
                    "weighted": round(weighted, 2) if weighted else None, "price": price,
                    "reverse": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in rev_out.items()}}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["init", "run"])
    ap.add_argument("run_dir")
    a = ap.parse_args()
    if a.cmd == "init":
        init(a.run_dir)
    else:
        with locked(os.path.join(run_paths(a.run_dir)["data"], "metrics.json")):
            run(a.run_dir)


if __name__ == "__main__":
    main()
