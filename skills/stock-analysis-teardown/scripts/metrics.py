#!/usr/bin/env python3
"""Every ratio in Part 2 of the playbook, computed in code from statements.json + market.json.

usage:
  metrics.py compute RUN_DIR [--dest DIR] [--years 5] [--adr-ratio N]
  metrics.py add     RUN_DIR KEY VALUE --unit pct|money_m|x|ps|days|num|ratio --source "10-K FY2026, note 15" --note "..."
  metrics.py get     RUN_DIR KEY [--fmt pct1]
  metrics.py list    RUN_DIR [SUBSTRING]

Writes metrics.json (series per fiscal year + one flat "values" map that slide tokens read)
and financials.md (a readable 5-year table for the analyst agents).
Money is in millions of the reporting currency. Percentages are fractions (0.51 = 51%).
Formulas live in references/metrics-definitions.md and in each value's "formula" field.

`add` is how agents record a number they found in a filing or a credible source
(segment revenue, non-GAAP EPS, backlog). It is stored in extra_metrics.json with a short
citation (document and page, or URL) and merged into metrics.json at once, so slides can use
it with a token like any other. The slide still carries the refs to the source.
"""
import argparse
import bisect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import currency_symbol, locked, log, parse_date, read_json, run_paths, today, update_run, write_json, write_text  # noqa: E402
from numfmt import fmt  # noqa: E402

STATUTORY_TAX = 0.21

SERIES_DEFS = {
    # key: (label, unit)
    "revenue": ("Revenue", "money_m"), "revenue_growth": ("Revenue growth", "pct"),
    "cost_of_revenue": ("Cost of revenue", "money_m"),
    "gross_profit": ("Gross profit", "money_m"), "gross_margin": ("Gross margin", "pct"),
    "gross_profit_growth": ("Gross profit growth", "pct"),
    "rnd": ("R&D", "money_m"), "rnd_pct": ("R&D as % of revenue", "pct"), "rnd_growth": ("R&D growth", "pct"),
    "sga": ("SG&A", "money_m"), "sga_pct": ("SG&A as % of revenue", "pct"), "sga_growth": ("SG&A growth", "pct"),
    "core_opex": ("Core opex (R&D + SG&A)", "money_m"), "core_opex_growth": ("Core opex growth", "pct"),
    "total_opex": ("Total operating expenses", "money_m"), "total_opex_growth": ("Total opex growth", "pct"),
    "opex_pct": ("Total opex as % of revenue", "pct"),
    "other_opex": ("Other operating expenses (amortization, restructuring, other)", "money_m"),
    "amort_intangibles": ("Amortization of acquired intangibles", "money_m"),
    "restructuring": ("Restructuring and other charges", "money_m"),
    "goodwill_impairment": ("Goodwill impairment", "money_m"),
    "operating_income": ("Operating income", "money_m"), "operating_margin": ("Operating margin", "pct"),
    "operating_income_growth": ("Operating income growth", "pct"),
    "incremental_operating_margin": ("Incremental operating margin", "pct"),
    "normalized_operating_income": ("Normalized operating income", "money_m"),
    "normalized_operating_margin": ("Normalized operating margin", "pct"),
    "dna": ("Depreciation and amortization", "money_m"), "depreciation": ("Depreciation", "money_m"),
    "ebitda": ("EBITDA", "money_m"), "ebitda_margin": ("EBITDA margin", "pct"),
    "adjusted_ebitda": ("EBITDA + stock-based compensation", "money_m"),
    "interest_expense": ("Interest expense", "money_m"),
    "pretax_income": ("Income before taxes", "money_m"), "income_tax": ("Income tax", "money_m"),
    "effective_tax_rate": ("Effective tax rate", "pct"),
    "net_income": ("Net income", "money_m"), "net_margin": ("Net margin", "pct"),
    "net_income_growth": ("Net income growth", "pct"),
    "gain_on_divestiture": ("Gain on sale of business", "money_m"),
    "net_income_ex_divestiture_gain": ("Net income excluding divestiture gain (after tax at 21%)", "money_m"),
    "eps_diluted": ("Diluted EPS", "ps"), "eps_growth": ("Diluted EPS growth", "pct"),
    "shares_diluted": ("Diluted weighted average shares", "shares_m"),
    "share_count_change": ("Change in diluted share count", "pct"),
    "dividends_per_share": ("Dividends declared per share", "ps"),
    "sbc": ("Stock-based compensation", "money_m"), "sbc_pct_revenue": ("SBC as % of revenue", "pct"),
    "sbc_pct_cfo": ("SBC as % of operating cash flow", "pct"),
    "cfo": ("Operating cash flow", "money_m"), "capex": ("Capital expenditure", "money_m"),
    "capex_pct_revenue": ("Capex as % of revenue", "pct"), "capex_to_depreciation": ("Capex / depreciation", "x"),
    "dna_pct_revenue": ("D&A as % of revenue", "pct"),
    "fcf": ("Free cash flow", "money_m"), "fcf_margin": ("FCF margin", "pct"), "fcf_growth": ("FCF growth", "pct"),
    "fcf_conversion": ("FCF / net income", "x"), "cfo_to_net_income": ("Operating cash flow / net income", "x"),
    "fcf_less_sbc": ("FCF minus SBC", "money_m"), "fcf_less_sbc_margin": ("FCF minus SBC margin", "pct"),
    "fcf_per_share": ("FCF per diluted share", "ps"),
    "acquisitions": ("Acquisitions, net of cash", "money_m"), "divestiture_proceeds": ("Divestiture proceeds", "money_m"),
    "buybacks": ("Share repurchases", "money_m"), "dividends_paid": ("Dividends paid", "money_m"),
    "shareholder_returns": ("Buybacks + dividends", "money_m"),
    "shareholder_returns_pct_fcf": ("Buybacks + dividends as % of FCF", "pct"),
    "debt_issued": ("Debt issued", "money_m"), "debt_repaid": ("Debt repaid", "money_m"),
    "cash": ("Cash and equivalents", "money_m"), "short_term_investments": ("Short-term investments", "money_m"),
    "cash_and_investments": ("Cash and short-term investments", "money_m"),
    "receivables": ("Accounts receivable", "money_m"), "inventory": ("Inventory", "money_m"),
    "payables": ("Accounts payable", "money_m"),
    "current_assets": ("Current assets", "money_m"), "current_liabilities": ("Current liabilities", "money_m"),
    "working_capital": ("Working capital", "money_m"),
    "operating_working_capital": ("Operating working capital (AR + inventory - AP)", "money_m"),
    "operating_working_capital_pct_revenue": ("Operating working capital as % of revenue", "pct"),
    "dso": ("Days sales outstanding", "days"), "dio": ("Days inventory outstanding", "days"),
    "dpo": ("Days payables outstanding", "days"), "ccc": ("Cash conversion cycle", "days"),
    "inventory_turnover": ("Inventory turnover", "x"),
    "current_ratio": ("Current ratio", "ratio"), "quick_ratio": ("Quick ratio", "ratio"),
    "ppe": ("PP&E, net", "money_m"), "goodwill": ("Goodwill", "money_m"), "intangibles": ("Intangible assets", "money_m"),
    "goodwill_and_intangibles": ("Goodwill and intangibles", "money_m"),
    "goodwill_intangibles_pct_assets": ("Goodwill and intangibles as % of assets", "pct"),
    "total_assets": ("Total assets", "money_m"), "total_liabilities": ("Total liabilities", "money_m"),
    "equity": ("Shareholders' equity", "money_m"),
    "short_term_debt": ("Short-term debt", "money_m"), "long_term_debt": ("Long-term debt", "money_m"),
    "total_debt": ("Total debt", "money_m"), "net_debt": ("Net debt (debt - cash and investments)", "money_m"),
    "net_debt_to_ebitda": ("Net debt / EBITDA", "x"), "debt_to_equity": ("Debt / equity", "ratio"),
    "interest_coverage": ("Interest coverage (EBIT / interest)", "x"),
    "invested_capital": ("Invested capital (equity + debt - cash)", "money_m"),
    "nopat": ("NOPAT", "money_m"), "roic": ("ROIC", "pct"), "roic_normalized": ("ROIC on normalized operating income", "pct"),
    "roe": ("ROE", "pct"), "roa": ("ROA", "pct"),
    "fy_end_price": ("Share price at fiscal year end", "ps"), "market_cap_hist": ("Market cap at fiscal year end", "money_m"),
    "pe_hist": ("P/E at fiscal year end", "x"), "ev_sales_hist": ("EV/Sales at fiscal year end", "x"),
    "ev_ebitda_hist": ("EV/EBITDA at fiscal year end", "x"), "p_fcf_hist": ("P/FCF at fiscal year end", "x"),
}


def safe_div(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b


def growth(cur, prev):
    if cur is None or prev is None or prev == 0:
        return None
    if prev < 0:
        return None  # growth off a negative base is not meaningful
    return cur / prev - 1.0


def cagr(first, last, years):
    if first is None or last is None or years <= 0 or first <= 0 or last <= 0:
        return None
    return (last / first) ** (1.0 / years) - 1.0


def avg(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return (a + b) / 2.0


def price_on_or_before(history, date):
    dates = [h["date"] for h in history]
    i = bisect.bisect_right(dates, date) - 1
    if i < 0:
        return None
    # only accept a close within 7 days of the target
    if (parse_date(date) - parse_date(dates[i])).days > 7:
        return None
    return history[i]["close"]


def split_factor(splits, period_end, filed):
    """Ratio to put an old per-share figure on today's share basis. A split counts if it came after
    the period ended and after the value was filed (later filings already restate)."""
    f = 1.0
    for s in splits or []:
        if s["date"] > period_end and (filed is None or s["date"] > filed):
            f *= s["ratio"]
    return f


def compute(run_dir, dest=None, years=5, adr_ratio=None):
    paths = run_paths(run_dir)
    dest = os.path.abspath(dest or paths["data"])
    st = read_json(os.path.join(dest, "statements.json"))
    if not st:
        sys.exit(f"no statements.json in {dest}; run fetch_sec.py first")
    mk = read_json(os.path.join(dest, "market.json"), {}) or {}
    run = read_json(paths["run_json"], {}) or {}
    is_main = os.path.abspath(dest) == os.path.abspath(paths["data"])
    if adr_ratio is None and is_main:
        adr_ratio = run.get("identity", {}).get("adr_ratio")
    adr = read_json(os.path.join(dest, "adr.json"), {}) or {}
    adr_warn = []
    if adr_ratio is None:
        adr_ratio = adr.get("ratio")
        if adr.get("status") == "not_found":
            adr_warn.append("20-F filer but no ADS ratio was found in the filing, so market cap and per-share "
                            "multiples assume one ADS = one share. Pass --adr-ratio N once the ratio is known.")
    adr_ratio = adr_ratio or 1.0

    periods = [p["label"] for p in st["annual"]["periods"]]
    pinfo = {p["label"]: p for p in st["annual"]["periods"]}
    items = st["annual"]["items"]
    splits = mk.get("splits") or []
    notes = []

    def raw(key, p):
        it = items.get(key)
        if not it:
            return None
        v = it["values"].get(p)
        if v is None:
            return None
        val = v["v"]
        kind = it.get("kind")
        if kind in ("per_share", "shares"):
            f = split_factor(splits, pinfo[p]["end"], v.get("filed"))
            if f != 1.0:
                val = val / f if kind == "per_share" else val * f
                notes.append(f"{key} {p} adjusted for stock split(s), factor {f:g}")
        if kind in ("flow", "instant"):
            return val / 1e6
        if kind == "shares":
            return val / 1e6
        return val

    S = {k: {} for k in SERIES_DEFS}
    formulas = {}
    for i, p in enumerate(periods):
        prev = periods[i - 1] if i > 0 else None
        g = lambda k, per=p: raw(k, per) if per else None  # noqa: E731
        rev, cogs = g("revenue"), g("cost_of_revenue")
        gp = g("gross_profit")
        if gp is None and rev is not None and cogs is not None:
            gp = rev - cogs
            formulas["gross_profit"] = "revenue - cost of revenue (company does not report gross profit)"
        if cogs is None and rev is not None and gp is not None:
            cogs = rev - gp
        rnd = g("rnd")
        sga = g("sga")
        if sga is None and g("selling_marketing") is not None and g("general_admin") is not None:
            sga = g("selling_marketing") + g("general_admin")
        op = g("operating_income")
        amort, restr, gwi = g("amort_intangibles"), g("restructuring"), g("goodwill_impairment")
        dep = g("depreciation")
        # D&A: a company's total D&A tag sometimes leaves out acquired-intangible amortization
        # (Marvell FY2022-23), so take the larger of the reported total and depreciation + amortization.
        cands = [x for x in (g("dna"), (dep + (amort or 0.0)) if dep is not None else None) if x is not None]
        dna = max(cands) if cands else None
        if dna is not None and g("dna") is not None and dna != g("dna"):
            formulas["dna"] = "max(reported D&A, depreciation + amortization of acquired intangibles)"
        ni, pretax, tax = g("net_income"), g("pretax_income"), g("income_tax")
        cfo, capex, sbc = g("cfo"), g("capex"), g("sbc")
        cash, sti = g("cash"), g("short_term_investments")
        ar, inv, ap = g("receivables"), g("inventory"), g("payables")
        ca, cl = g("current_assets"), g("current_liabilities")
        gw, intang, ta, tl, eq = g("goodwill"), g("intangibles"), g("total_assets"), g("total_liabilities"), g("equity")
        std, ltd, ltd_total = g("short_term_debt"), g("long_term_debt"), g("long_term_debt_total")
        if ltd is not None:
            total_debt = ltd + (std or 0.0)
        elif ltd_total is not None:
            total_debt = ltd_total
            formulas["total_debt"] = "LongTermDebt tag (includes current portion); check the debt note"
        else:
            total_debt = std
        shares_d, eps_d = g("shares_diluted"), g("eps_diluted")

        def put(k, v):
            if v is not None:
                S[k][p] = v

        put("revenue", rev); put("cost_of_revenue", cogs); put("gross_profit", gp)
        put("gross_margin", safe_div(gp, rev))
        put("rnd", rnd); put("rnd_pct", safe_div(rnd, rev))
        put("sga", sga); put("sga_pct", safe_div(sga, rev))
        core = (rnd + sga) if rnd is not None and sga is not None else None
        put("core_opex", core)
        tot = (gp - op) if gp is not None and op is not None else None
        put("total_opex", tot); put("opex_pct", safe_div(tot, rev))
        put("other_opex", (tot - core) if tot is not None and core is not None else None)
        put("amort_intangibles", amort); put("restructuring", restr); put("goodwill_impairment", gwi)
        put("operating_income", op); put("operating_margin", safe_div(op, rev))
        norm = op + (amort or 0) + (restr or 0) + (gwi or 0) if op is not None else None
        put("normalized_operating_income", norm); put("normalized_operating_margin", safe_div(norm, rev))
        put("dna", dna); put("depreciation", dep)
        ebitda = op + dna if op is not None and dna is not None else None
        put("ebitda", ebitda); put("ebitda_margin", safe_div(ebitda, rev))
        put("adjusted_ebitda", ebitda + sbc if ebitda is not None and sbc is not None else None)
        put("interest_expense", g("interest_expense"))
        put("pretax_income", pretax); put("income_tax", tax)
        etr = safe_div(tax, pretax) if pretax and pretax > 0 else None
        put("effective_tax_rate", etr)
        put("net_income", ni); put("net_margin", safe_div(ni, rev))
        gain = g("gain_on_divestiture")
        put("gain_on_divestiture", gain)
        if ni is not None and gain:
            put("net_income_ex_divestiture_gain", ni - gain * (1 - STATUTORY_TAX))
        put("eps_diluted", eps_d); put("shares_diluted", shares_d)
        put("dividends_per_share", g("dividends_per_share"))
        put("sbc", sbc); put("sbc_pct_revenue", safe_div(sbc, rev)); put("sbc_pct_cfo", safe_div(sbc, cfo))
        put("cfo", cfo); put("capex", capex)
        put("capex_pct_revenue", safe_div(capex, rev)); put("capex_to_depreciation", safe_div(capex, dep))
        put("dna_pct_revenue", safe_div(dna, rev))
        fcf = cfo - capex if cfo is not None and capex is not None else None
        put("fcf", fcf); put("fcf_margin", safe_div(fcf, rev))
        put("fcf_conversion", safe_div(fcf, ni) if ni and ni > 0 else None)
        put("cfo_to_net_income", safe_div(cfo, ni) if ni and ni > 0 else None)
        put("fcf_less_sbc", fcf - sbc if fcf is not None and sbc is not None else None)
        put("fcf_less_sbc_margin", safe_div(fcf - sbc, rev) if fcf is not None and sbc is not None else None)
        put("fcf_per_share", safe_div(fcf, shares_d))
        for k in ("acquisitions", "divestiture_proceeds", "buybacks", "dividends_paid", "debt_issued", "debt_repaid"):
            put(k, g(k))
        sr = (g("buybacks") or 0) + (g("dividends_paid") or 0)
        put("shareholder_returns", sr)
        put("shareholder_returns_pct_fcf", safe_div(sr, fcf) if fcf and fcf > 0 else None)
        put("cash", cash); put("short_term_investments", sti)
        cash_inv = (cash or 0) + (sti or 0) if cash is not None else None
        put("cash_and_investments", cash_inv)
        put("receivables", ar); put("inventory", inv); put("payables", ap)
        put("current_assets", ca); put("current_liabilities", cl)
        put("working_capital", ca - cl if ca is not None and cl is not None else None)
        onwc = (ar or 0) + (inv or 0) - (ap or 0) if ar is not None else None
        put("operating_working_capital", onwc); put("operating_working_capital_pct_revenue", safe_div(onwc, rev))
        put("dso", safe_div(ar, rev) * 365 if safe_div(ar, rev) is not None else None)
        put("dio", safe_div(inv, cogs) * 365 if safe_div(inv, cogs) is not None and inv else None)
        put("dpo", safe_div(ap, cogs) * 365 if safe_div(ap, cogs) is not None else None)
        if p in S["dso"] and p in S["dpo"]:
            put("ccc", S["dso"][p] + S["dio"].get(p, 0.0) - S["dpo"][p])
        put("inventory_turnover", safe_div(cogs, inv) if inv else None)
        put("current_ratio", safe_div(ca, cl))
        put("quick_ratio", safe_div((cash_inv or 0) + (ar or 0), cl) if cl else None)
        put("ppe", g("ppe")); put("goodwill", gw); put("intangibles", intang)
        gwi_total = (gw or 0) + (intang or 0) if (gw is not None or intang is not None) else None
        put("goodwill_and_intangibles", gwi_total)
        put("goodwill_intangibles_pct_assets", safe_div(gwi_total, ta))
        put("total_assets", ta); put("total_liabilities", tl); put("equity", eq)
        put("short_term_debt", std); put("long_term_debt", ltd if ltd is not None else ltd_total)
        put("total_debt", total_debt)
        net_debt = total_debt - cash_inv if total_debt is not None and cash_inv is not None else None
        put("net_debt", net_debt)
        put("net_debt_to_ebitda", safe_div(net_debt, ebitda) if ebitda and ebitda > 0 else None)
        put("debt_to_equity", safe_div(total_debt, eq) if eq and eq > 0 else None)
        ie = g("interest_expense")
        put("interest_coverage", safe_div(op, ie) if ie and ie > 0 else None)
        ic = eq + (total_debt or 0) - (cash_inv or 0) if eq is not None else None
        put("invested_capital", ic)
        t = min(max(etr, 0.0), 0.35) if etr is not None else STATUTORY_TAX
        nopat = op * (1 - t) if op is not None else None
        put("nopat", nopat)
        if prev:
            for k, base in (("revenue_growth", "revenue"), ("gross_profit_growth", "gross_profit"),
                            ("rnd_growth", "rnd"), ("sga_growth", "sga"), ("core_opex_growth", "core_opex"),
                            ("total_opex_growth", "total_opex"), ("operating_income_growth", "operating_income"),
                            ("net_income_growth", "net_income"), ("eps_growth", "eps_diluted"), ("fcf_growth", "fcf")):
                put(k, growth(S[base].get(p), S[base].get(prev)))
            put("share_count_change", growth(S["shares_diluted"].get(p), S["shares_diluted"].get(prev)))
            if rev is not None and S["revenue"].get(prev) is not None and op is not None and S["operating_income"].get(prev) is not None:
                drev = rev - S["revenue"][prev]
                if abs(drev) > 1e-9:
                    put("incremental_operating_margin", (op - S["operating_income"][prev]) / drev)
            avg_ic = avg(ic, S["invested_capital"].get(prev))
            if avg_ic and avg_ic > 0:
                put("roic", safe_div(nopat, avg_ic))
                if norm is not None:
                    put("roic_normalized", norm * (1 - t) / avg_ic)
            avg_eq = avg(eq, S["equity"].get(prev))
            put("roe", safe_div(ni, avg_eq) if avg_eq and avg_eq > 0 else None)
            put("roa", safe_div(ni, avg(ta, S["total_assets"].get(prev))))

    # ---- market + valuation snapshot
    rep_ccy = st["meta"]["currency"]
    px_ccy = mk.get("currency") or rep_ccy
    fx = (mk.get("fx") or {}).get("rate") or 1.0 if px_ccy != rep_ccy else 1.0
    lb = st.get("latest_balance", {}).get("items", {})
    lbv = lambda k: (lb[k]["v"] / 1e6) if k in lb else None  # noqa: E731
    shares_now = lbv("shares_outstanding_cover") or lbv("shares_outstanding")
    if shares_now is None and periods:
        shares_now = S["shares_diluted"].get(periods[-1])
    ttm_items = st.get("ttm", {}).get("items", {})
    ttm = {k: v / 1e6 for k, v in ttm_items.items()}
    if "depreciation" in ttm:
        ttm["dna"] = max(ttm.get("dna", 0.0), ttm["depreciation"] + ttm.get("amort_intangibles", 0.0))
    if "gross_profit" not in ttm and "revenue" in ttm and "cost_of_revenue" in ttm:
        ttm["gross_profit"] = ttm["revenue"] - ttm["cost_of_revenue"]
    ttm_fcf = ttm["cfo"] - ttm["capex"] if "cfo" in ttm and "capex" in ttm else None
    ttm_ebitda = ttm["operating_income"] + ttm["dna"] if "operating_income" in ttm and "dna" in ttm else None

    V = {}

    def val(key, v, unit, label, formula=None, src="calc", source=None, ccy=None):
        if v is None:
            return
        V[key] = {"v": v, "unit": unit, "label": label}
        if ccy and ccy != rep_ccy:
            V[key]["ccy"] = ccy
        if formula:
            V[key]["formula"] = formula
        if src != "calc":
            V[key]["src"] = src
        if source:
            V[key]["source"] = source

    disp = periods[-years:] if len(periods) >= years else periods
    first, last = (disp[0], disp[-1]) if disp else (None, None)
    n_years = len(disp) - 1
    for k in ("revenue", "gross_profit", "operating_income", "normalized_operating_income", "net_income", "eps_diluted",
              "cfo", "fcf", "sbc", "rnd", "sga", "core_opex", "dividends_per_share", "shares_diluted", "ebitda"):
        if first and last:
            c = cagr(S[k].get(first), S[k].get(last), n_years)
            val(f"{k}_cagr", c, "pct", f"{SERIES_DEFS[k][0]} CAGR {first} to {last}",
                f"({k}[{last}] / {k}[{first}]) ^ (1/{n_years}) - 1")
            ch = growth(S[k].get(last), S[k].get(first))
            val(f"{k}_change", ch, "pct", f"{SERIES_DEFS[k][0]} total change {first} to {last}")
    if len(periods) >= 10:
        c = cagr(S["revenue"].get(periods[-10]), S["revenue"].get(periods[-1]), 9)
        val("revenue_cagr_10y", c, "pct", f"Revenue CAGR {periods[-10]} to {periods[-1]}")
    for k in ("cfo", "capex", "fcf", "sbc", "acquisitions", "divestiture_proceeds", "buybacks", "dividends_paid",
              "debt_issued", "debt_repaid", "net_income", "shareholder_returns"):
        tot = sum(S[k].get(p, 0.0) for p in disp)
        val(f"cum_{k}", tot, "money_m", f"{SERIES_DEFS[k][0]}, cumulative {first} to {last}")
    if first and S["shares_diluted"].get(first) and S["shares_diluted"].get(last):
        val("dilution_total", growth(S["shares_diluted"][last], S["shares_diluted"][first]), "pct",
            f"Change in diluted share count {first} to {last}")

    # TTM
    for k, lbl in (("revenue", "Revenue"), ("gross_profit", "Gross profit"), ("operating_income", "Operating income"),
                   ("net_income", "Net income"), ("cfo", "Operating cash flow"), ("capex", "Capex"), ("sbc", "SBC"),
                   ("dna", "D&A"), ("rnd", "R&D"), ("sga", "SG&A")):
        if k in ttm:
            val(f"{k}@TTM", ttm[k], "money_m", f"{lbl}, trailing twelve months to {st['ttm'].get('as_of')}")
    val("fcf@TTM", ttm_fcf, "money_m", "Free cash flow, trailing twelve months", "cfo - capex")
    val("ebitda@TTM", ttm_ebitda, "money_m", "EBITDA, trailing twelve months", "operating income + D&A")
    if "revenue" in ttm:
        val("gross_margin@TTM", safe_div(ttm.get("gross_profit"), ttm["revenue"]), "pct", "Gross margin, TTM")
        val("operating_margin@TTM", safe_div(ttm.get("operating_income"), ttm["revenue"]), "pct", "Operating margin, TTM")
        val("net_margin@TTM", safe_div(ttm.get("net_income"), ttm["revenue"]), "pct", "Net margin, TTM")
        val("fcf_margin@TTM", safe_div(ttm_fcf, ttm["revenue"]), "pct", "FCF margin, TTM")
        if last and S["revenue"].get(last):
            # TTM growth vs the same window a year earlier needs the prior TTM; approximate with last FY when equal
            pass
    q_rev = (st.get("quarterly", {}).get("items", {}).get("revenue") or {}).get("values", {})
    q_ends = {p["label"]: p["end"] for p in st.get("quarterly", {}).get("periods", [])}
    q_order = [p["label"] for p in st.get("quarterly", {}).get("periods", []) if p["label"] in q_rev]
    # keep only the unbroken run of quarters that ends with the latest one; a missing quarter would make
    # "the last four" span more than a year
    run = q_order[-1:]
    for lbl in reversed(q_order[:-1]):
        gap = (parse_date(q_ends[run[0]]) - parse_date(q_ends[lbl])).days
        if not 75 <= gap <= 105:
            break
        run.insert(0, lbl)
    q_order = run
    if len(q_order) >= 8:
        cur4 = sum(q_rev[q]["v"] for q in q_order[-4:]) / 1e6
        prev4 = sum(q_rev[q]["v"] for q in q_order[-8:-4]) / 1e6
        val("revenue_growth@TTM", growth(cur4, prev4), "pct",
            f"Revenue growth, last four quarters ({q_order[-4]} to {q_order[-1]}) vs the four before")
    if len(q_order) >= 5:
        val("revenue_growth@LATEST_Q_YOY", growth(q_rev[q_order[-1]]["v"], q_rev[q_order[-5]]["v"]), "pct",
            f"Revenue growth, {q_order[-1]} vs {q_order[-5]}")
    sh_ttm = ttm.get("shares_diluted") or (S["shares_diluted"].get(last) if last else None)
    eps_ttm = safe_div(ttm.get("net_income"), sh_ttm)
    val("eps@TTM", eps_ttm, "ps", "EPS, TTM (TTM net income / latest diluted weighted shares)")
    val("shares_diluted@TTM", sh_ttm, "shares_m", "Diluted weighted shares, latest reported period")

    # latest balance sheet
    lb_date = st.get("latest_balance", {}).get("date")
    cash_l = (lbv("cash") or 0) + (lbv("short_term_investments") or 0) if lbv("cash") is not None else None
    if lbv("long_term_debt") is not None:
        debt_l = lbv("long_term_debt") + (lbv("short_term_debt") or 0)
    else:
        debt_l = lbv("long_term_debt_total") if lbv("long_term_debt_total") is not None else lbv("short_term_debt")
    eq_l = lbv("equity")
    for k, v, lbl in (("cash_and_investments@LATEST", cash_l, "Cash and short-term investments"),
                      ("total_debt@LATEST", debt_l, "Total debt"), ("equity@LATEST", eq_l, "Shareholders' equity"),
                      ("goodwill@LATEST", lbv("goodwill"), "Goodwill"),
                      ("receivables@LATEST", lbv("receivables"), "Accounts receivable"),
                      ("inventory@LATEST", lbv("inventory"), "Inventory")):
        val(k, v, "money_m", f"{lbl} at {lb_date}")
    net_debt_l = debt_l - cash_l if debt_l is not None and cash_l is not None else None
    val("net_debt@LATEST", net_debt_l, "money_m", f"Net debt at {lb_date}")
    val("net_debt_to_ebitda@LATEST", safe_div(net_debt_l, ttm_ebitda) if ttm_ebitda and ttm_ebitda > 0 else None,
        "x", "Net debt / TTM EBITDA")
    val("shares_outstanding@LATEST", shares_now, "shares_m", "Shares outstanding (latest cover page)")

    price = mk.get("price")
    if price:
        price_per_share = price / adr_ratio
        mcap_px = price_per_share * shares_now if shares_now else None   # in price currency, millions
        mcap = mcap_px / fx if mcap_px is not None else None             # in reporting currency
        ev = mcap + (debt_l or 0) - (cash_l or 0) if mcap is not None else None
        val("price", price, "ps", f"Share price ({px_ccy}) at {mk.get('price_time', '')[:10]}", src="market",
            source=mk.get("source_url"), ccy=px_ccy)
        val("market_cap", mcap_px, "money_m", f"Market cap ({px_ccy})", "price x shares outstanding", ccy=px_ccy)
        val("market_cap_reporting", mcap, "money_m", f"Market cap in reporting currency ({rep_ccy})")
        val("enterprise_value", ev, "money_m", "Enterprise value", "market cap + debt - cash and investments")
        val("pe_ttm", safe_div(mcap, ttm.get("net_income")) if ttm.get("net_income", 0) > 0 else None, "x", "P/E, TTM")
        val("ev_ebitda_ttm", safe_div(ev, ttm_ebitda) if ttm_ebitda and ttm_ebitda > 0 else None, "x", "EV/EBITDA, TTM")
        val("ev_sales_ttm", safe_div(ev, ttm.get("revenue")), "x", "EV/Sales, TTM")
        val("p_fcf_ttm", safe_div(mcap, ttm_fcf) if ttm_fcf and ttm_fcf > 0 else None, "x", "Price/FCF, TTM")
        val("fcf_yield_ttm", safe_div(ttm_fcf, mcap), "pct", "FCF yield, TTM")
        val("p_b", safe_div(mcap, eq_l) if eq_l and eq_l > 0 else None, "x", "Price/book")
        val("p_s_ttm", safe_div(mcap, ttm.get("revenue")), "x", "Price/sales, TTM")
        val("dividend_yield", safe_div(mk.get("trailing_dividends_12m"), price), "pct", "Dividend yield, trailing 12 months")
        val("high_52w", mk.get("high_52w"), "ps", "52-week high", ccy=px_ccy)
        val("low_52w", mk.get("low_52w"), "ps", "52-week low", ccy=px_ccy)
        val("off_52w_high", safe_div(price, mk.get("high_52w")) - 1 if mk.get("high_52w") else None, "pct", "Distance from 52-week high")
        for k in ("1y", "3y", "5y"):
            val(f"return_{k}", (mk.get("returns") or {}).get(k), "pct", f"Total return, {k}")
            val(f"benchmark_return_{k}", (mk.get("benchmark_returns") or {}).get(k), "pct", f"S&P 500 (SPY) total return, {k}")
        val("beta", (mk.get("beta") or {}).get("value"), "ratio", "Beta vs SPY (weekly, up to 5 years)")
        val("volatility_1y", mk.get("volatility_1y"), "pct", "Annualized volatility, 1 year")
        val("max_drawdown_5y", (mk.get("drawdown_5y") or {}).get("max_drawdown"), "pct", "Maximum drawdown, 5 years")
        val("risk_free_rate", (mk.get("risk_free") or {}).get("value"), "pct", "US 10-year Treasury yield")

        # historical multiples at each fiscal year end
        hist = mk.get("history") or []
        for p in periods:
            px = price_on_or_before(hist, pinfo[p]["end"])
            if px is None:
                continue
            px_ps = px / adr_ratio
            sh = S["shares_diluted"].get(p)
            if not sh:
                continue
            mc = px_ps * sh / fx
            S["fy_end_price"][p] = px
            S["market_cap_hist"][p] = mc
            ev_h = mc + (S["total_debt"].get(p) or 0) - (S["cash_and_investments"].get(p) or 0)
            ni_p, rev_p, eb_p, f_p = (S["net_income"].get(p), S["revenue"].get(p), S["ebitda"].get(p), S["fcf"].get(p))
            if ni_p and ni_p > 0:
                S["pe_hist"][p] = mc / ni_p
            if rev_p:
                S["ev_sales_hist"][p] = ev_h / rev_p
            if eb_p and eb_p > 0:
                S["ev_ebitda_hist"][p] = ev_h / eb_p
            if f_p and f_p > 0:
                S["p_fcf_hist"][p] = mc / f_p
        for k, cur in (("ev_sales_hist", "ev_sales_ttm"), ("ev_ebitda_hist", "ev_ebitda_ttm"), ("pe_hist", "pe_ttm"),
                       ("p_fcf_hist", "p_fcf_ttm")):
            vals = [S[k][p] for p in disp if p in S[k]]
            if len(vals) >= 2:
                val(f"{k}_avg", sum(vals) / len(vals), "x", f"{SERIES_DEFS[k][0]}, average {disp[0]} to {disp[-1]} ({len(vals)} years)")

    # flatten series into values
    for k, per in S.items():
        label, unit = SERIES_DEFS[k]
        for p, v in per.items():
            V[f"{k}@{p}"] = {"v": v, "unit": unit, "label": f"{label}, {p}"}

    # merge agent-recorded values
    extra = read_json(os.path.join(dest, "extra_metrics.json"), {}) or {}
    for k, e in extra.items():
        V[k] = {**e, "src": "agent"}

    sanity_warn = []
    pe_v = (V.get("pe_ttm") or {}).get("v")
    mc_v = (V.get("market_cap") or {}).get("v")
    if (px_ccy != rep_ccy or adr_ratio != 1.0) and pe_v and pe_v > 120:
        sanity_warn.append(f"P/E TTM is {pe_v:.0f}x with the price in {px_ccy} and the accounts in {rep_ccy} "
                           f"(ADS ratio {adr_ratio:g}). Confirm the ADS ratio and the FX rate before using any multiple.")
    if mc_v and px_ccy == "USD" and mc_v > 6e6:
        sanity_warn.append(f"Market cap comes out at ${mc_v / 1e6:.1f}T, above any listed company. Check the ADS ratio "
                           f"and the share count.")
    meta = {
        "ticker": st["meta"].get("ticker"), "name": st["meta"].get("name"), "currency": rep_ccy,
        "currency_symbol": currency_symbol(rep_ccy), "price_currency": px_ccy, "price_currency_symbol": currency_symbol(px_ccy),
        "fx_reporting_to_price": fx, "adr_ratio": adr_ratio,
        "periods": periods, "display_periods": disp, "fiscal_period_ends": {p: pinfo[p]["end"] for p in periods},
        "ttm_as_of": st.get("ttm", {}).get("as_of"), "ttm_method": st.get("ttm", {}).get("method"),
        "latest_balance_date": lb_date, "price_time": mk.get("price_time"),
        "generated": today(), "units": "money in millions of reporting currency; pct as fraction",
        "debt_maturities": {k: v["v"] / 1e6 for k, v in ((st.get("debt_maturities") or {}).get("items") or {}).items()},
        "debt_maturities_as_of": (st.get("debt_maturities") or {}).get("as_of"),
        "warnings": st.get("warnings", []) + adr_warn + sanity_warn,
        "adr_evidence": adr.get("evidence") if adr.get("status") == "found" else None,
    }
    out = {"meta": meta,
           "series": {k: {"label": SERIES_DEFS[k][0], "unit": SERIES_DEFS[k][1], "values": v} for k, v in S.items() if v},
           "quarterly": {k: {p: v["v"] / 1e6 for p, v in it["values"].items()} for k, it in st.get("quarterly", {}).get("items", {}).items()
                         if k in ("revenue", "gross_profit", "operating_income", "net_income", "cfo", "capex")},
           "quarter_periods": [p["label"] for p in st.get("quarterly", {}).get("periods", [])],
           "values": V, "formulas": formulas, "notes": sorted(set(notes))}
    write_json(os.path.join(dest, "metrics.json"), out)
    write_text(os.path.join(dest, "financials.md"), financials_md(out))
    if is_main:
        update_run(run_dir, phases={"metrics": "done"})
    log(f"metrics.json: {len(V)} values, display {disp[0] if disp else ''}..{disp[-1] if disp else ''}; "
        f"price {price}; P/E TTM {V.get('pe_ttm', {}).get('v')}")
    return out


def financials_md(m):
    meta = m["meta"]
    sym = meta["currency_symbol"]
    disp = meta["display_periods"]
    rows = [
        ("Revenue", "revenue", "money_m"), ("Revenue growth", "revenue_growth", "pct"),
        ("Gross margin", "gross_margin", "pct"), ("Operating income", "operating_income", "money_m"),
        ("Operating margin", "operating_margin", "pct"), ("Normalized operating margin", "normalized_operating_margin", "pct"),
        ("Net income", "net_income", "money_m"), ("Net margin", "net_margin", "pct"), ("Diluted EPS", "eps_diluted", "ps"),
        ("R&D % revenue", "rnd_pct", "pct"), ("SG&A % revenue", "sga_pct", "pct"), ("SBC % revenue", "sbc_pct_revenue", "pct"),
        ("Operating cash flow", "cfo", "money_m"), ("Capex", "capex", "money_m"), ("Free cash flow", "fcf", "money_m"),
        ("FCF margin", "fcf_margin", "pct"), ("FCF minus SBC", "fcf_less_sbc", "money_m"),
        ("DSO (days)", "dso", "days"), ("DIO (days)", "dio", "days"), ("DPO (days)", "dpo", "days"), ("Cash conversion cycle", "ccc", "days"),
        ("Cash + ST investments", "cash_and_investments", "money_m"), ("Total debt", "total_debt", "money_m"),
        ("Net debt", "net_debt", "money_m"), ("Net debt / EBITDA", "net_debt_to_ebitda", "x"),
        ("Goodwill + intangibles % assets", "goodwill_intangibles_pct_assets", "pct"),
        ("ROIC", "roic", "pct"), ("ROIC (normalized)", "roic_normalized", "pct"), ("ROE", "roe", "pct"),
        ("Diluted shares (M)", "shares_diluted", "shares_m"), ("Buybacks", "buybacks", "money_m"),
        ("Acquisitions", "acquisitions", "money_m"),
    ]
    out = [f"# {meta['name']} ({meta['ticker']}) key financials", "",
           f"Money in millions of {meta['currency']}. Source SEC XBRL filings; ratios computed by metrics.py. Generated {meta['generated']}.", "",
           "| Line | " + " | ".join(disp) + " | Token key |", "|---|" + "---|" * len(disp) + "---|"]
    for label, key, unit in rows:
        s = m["series"].get(key, {}).get("values", {})
        cells = [fmt(s.get(p), unit, sym=sym) if s.get(p) is not None else "n/a" for p in disp]
        out.append(f"| {label} | " + " | ".join(cells) + f" | `{key}@<period>` |")
    out += ["", "## Snapshot", ""]
    for k in ("price", "market_cap", "enterprise_value", "pe_ttm", "ev_ebitda_ttm", "ev_sales_ttm", "p_fcf_ttm", "fcf_yield_ttm",
              "revenue@TTM", "fcf@TTM", "net_debt@LATEST", "beta", "return_1y", "revenue_cagr", "dilution_total"):
        v = m["values"].get(k)
        if v:
            out.append(f"- `{k}` {fmt(v['v'], v['unit'], sym=currency_symbol(v.get('ccy') or meta['currency']))}  ({v['label']})")
    if meta.get("warnings"):
        out += ["", "## Data warnings", ""] + [f"- {w}" for w in meta["warnings"]]
    if m.get("notes"):
        out += ["", "## Adjustments", ""] + [f"- {n}" for n in m["notes"]]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compute"); c.add_argument("run_dir"); c.add_argument("--dest"); c.add_argument("--years", type=int, default=5)
    c.add_argument("--adr-ratio", type=float, default=None)
    a = sub.add_parser("add"); a.add_argument("run_dir"); a.add_argument("key"); a.add_argument("value", type=float)
    a.add_argument("--unit", required=True); a.add_argument("--source", required=True); a.add_argument("--note", default="")
    a.add_argument("--label", default=None); a.add_argument("--dest")
    gp = sub.add_parser("get"); gp.add_argument("run_dir"); gp.add_argument("key"); gp.add_argument("--fmt"); gp.add_argument("--dest")
    ls = sub.add_parser("list"); ls.add_argument("run_dir"); ls.add_argument("pattern", nargs="?", default=""); ls.add_argument("--dest")
    args = ap.parse_args()
    paths = run_paths(args.run_dir)
    dest = os.path.abspath(getattr(args, "dest", None) or paths["data"])

    if args.cmd == "compute":
        if args.adr_ratio:
            from _common import update_run as ur
            run = read_json(paths["run_json"], {})
            ident = run.get("identity", {}); ident["adr_ratio"] = args.adr_ratio
            ur(args.run_dir, identity=ident)
        with locked(os.path.join(dest, "metrics.json")):
            compute(args.run_dir, args.dest, args.years, args.adr_ratio)
        if dest == os.path.abspath(paths["data"]):
            # compute rewrites metrics.json from scratch, so put the peer and valuation tokens back
            import subprocess
            here = os.path.dirname(os.path.abspath(__file__))
            if os.path.exists(os.path.join(dest, "peers.json")):
                subprocess.run([sys.executable, os.path.join(here, "peers.py"), "build", args.run_dir], check=False)
            if os.path.exists(os.path.join(dest, "valuation.json")):
                subprocess.run([sys.executable, os.path.join(here, "valuation.py"), "run", args.run_dir], check=False)
    elif args.cmd == "add":
        units = {"pct", "money_m", "x", "ps", "days", "num", "ratio", "shares_m", "pp"}
        if args.unit not in units:
            sys.exit(f"unit must be one of {sorted(units)}")
        path = os.path.join(dest, "extra_metrics.json")
        with locked(os.path.join(dest, "metrics.json")):
            extra = read_json(path, {}) or {}
            extra[args.key] = {"v": args.value, "unit": args.unit, "label": args.label or args.note or args.key,
                               "source": args.source, "note": args.note, "added": today()}
            write_json(path, extra)
            m = read_json(os.path.join(dest, "metrics.json"))
            if m is not None:
                m["values"][args.key] = {**extra[args.key], "src": "agent"}
                write_json(os.path.join(dest, "metrics.json"), m)
        print(f"recorded {args.key} = {args.value} ({args.unit}) source {args.source}")
    elif args.cmd == "get":
        m = read_json(os.path.join(dest, "metrics.json"))
        v = m["values"].get(args.key)
        if not v:
            sys.exit(f"no value for {args.key}")
        print(fmt(v["v"], v["unit"], args.fmt, sym=currency_symbol(v.get("ccy") or m["meta"]["currency"])), "|", v["v"], "|", v.get("label"))
    elif args.cmd == "list":
        m = read_json(os.path.join(dest, "metrics.json"))
        for k in sorted(m["values"]):
            if args.pattern in k:
                v = m["values"][k]
                print(f"{k:48s} {fmt(v['v'], v['unit'], sym=currency_symbol(v.get('ccy') or m['meta']['currency'])):>14s}  {v.get('label', '')}")


if __name__ == "__main__":
    main()
