"""One place that turns numbers into text, so slides, tables and checks agree.

Token syntax used in deck text:  {{m:KEY}}  or  {{m:KEY|FORMAT}}
  KEY     a key in metrics.json "values", e.g. revenue@FY2026, gross_margin@FY2026, revenue_cagr, pe_ttm
  FORMAT  optional, one of the specs below; the unit's default is used when omitted

Specs
  pct pct1 pct2      51% / 51.0% / 51.04%         (value stored as a fraction, 0.51)
  pp pp1             +3 pp / +3.2 pp              (difference of two fractions)
  money              auto: $820M, $8.2B, $1.2T    (value stored in millions)
  money_m            $8,195M
  money_b money_b2   $8.2B / $8.19B
  ps ps0             $3.07 / $3                   (per-share amounts)
  x x0 x2            24.3x / 24x / 24.31x
  num num1 num2      1,234 / 1,234.5 / 1.23
  shares             870M shares                   (value stored in millions)
  days               45 days
  bare               the number with no symbol, sensible decimals
Append "+" to any spec to force a sign on positive values: pct1+ -> +42.1%
"""

MINUS = "−"
DEFAULT_SPEC = {"money_m": "money", "pct": "pct1", "x": "x", "days": "days", "ps": "ps", "shares_m": "shares",
                "ratio": "num2", "num": "num", "pp": "pp1", "years": "num1"}


def _sign(v, force):
    if v < 0:
        return MINUS
    return "+" if force and v > 0 else ""


def fmt(v, unit="num", spec=None, sym="$"):
    if v is None:
        return "n/a"
    spec = spec or DEFAULT_SPEC.get(unit, "num")
    force = spec.endswith("+")
    spec = spec.rstrip("+")
    s = _sign(v, force)
    a = abs(v)
    if spec in ("pct", "pct1", "pct2"):
        d = {"pct": 0, "pct1": 1, "pct2": 2}[spec]
        return f"{s}{a * 100:,.{d}f}%"
    if spec in ("pp", "pp1"):
        d = 0 if spec == "pp" else 1
        s = _sign(v, True)
        return f"{s}{a * 100:,.{d}f} pp"
    if spec == "money":
        if a == 0:
            return f"{sym}0"
        if a >= 1_000_000:
            return f"{s}{sym}{a / 1_000_000:,.1f}T"
        if a >= 1000:
            return f"{s}{sym}{a / 1000:,.{2 if a < 10_000 else 1}f}B".replace(".00B", "B")
        return f"{s}{sym}{a:,.0f}M" if a >= 10 else f"{s}{sym}{a:,.1f}M"
    if spec == "money_m":
        return f"{s}{sym}{a:,.0f}M"
    if spec in ("money_b", "money_b2"):
        d = 1 if spec == "money_b" else 2
        return f"{s}{sym}{a / 1000:,.{d}f}B"
    if spec in ("ps", "ps0"):
        d = 2 if spec == "ps" else 0
        return f"{s}{sym}{a:,.{d}f}"
    if spec in ("x", "x0", "x2"):
        d = {"x": 1, "x0": 0, "x2": 2}[spec]
        return f"{s}{a:,.{d}f}x"
    if spec in ("num", "num1", "num2"):
        d = {"num": 0, "num1": 1, "num2": 2}[spec]
        return f"{s}{a:,.{d}f}"
    if spec == "shares":
        return f"{s}{a:,.0f}M shares" if a >= 10 else f"{s}{a:,.1f}M shares"
    if spec == "days":
        return f"{s}{a:,.0f} days"
    if spec == "bare":
        if unit == "pct":
            return f"{s}{a * 100:,.1f}"
        return f"{s}{a:,.2f}" if a < 100 else f"{s}{a:,.0f}"
    raise ValueError(f"unknown format spec '{spec}'")


def parse_token(tok):
    """'revenue@FY2026|money' -> ('revenue@FY2026', 'money')"""
    key, _, spec = tok.partition("|")
    return key.strip(), (spec.strip() or None)
