"""Shared helpers for the stock-analysis-teardown scripts. Python 3 standard library only."""
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

SEC_UA = os.environ.get("SEC_USER_AGENT", "stock-analysis-teardown research@example.com")
BROWSER_UA = "Mozilla/5.0"  # Yahoo rate-limits full browser strings; the short form works

_last_call = {"sec": 0.0, "other": 0.0}


def log(*args):
    print(*args, file=sys.stderr, flush=True)


def http_get(url, ua=None, retries=4, timeout=60, accept=None):
    """GET with a polite rate limit for sec.gov (max ~8 requests a second) and retries."""
    host_kind = "sec" if "sec.gov" in url else "other"
    min_gap = 0.13 if host_kind == "sec" else 0.05
    headers = {"User-Agent": ua or (SEC_UA if host_kind == "sec" else BROWSER_UA)}
    if accept:
        headers["Accept"] = accept
    last_err = None
    for attempt in range(retries):
        wait = _last_call[host_kind] + min_gap - time.time()
        if wait > 0:
            time.sleep(wait)
        _last_call[host_kind] = time.time()
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (404, 400, 401, 403) and attempt >= 1:
                break
            time.sleep(1.5 * (attempt + 1))
        except Exception as e:  # network hiccup
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET failed for {url}: {last_err}")


def get_json(url, **kw):
    return json.loads(http_get(url, **kw).decode("utf-8"))


def cached_json(url, path, refresh=False, **kw):
    """Fetch JSON once and keep the raw copy on disk so reruns are fast and auditable."""
    if not refresh and os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    data = get_json(url, **kw)
    write_json(path, data)
    return data


def write_json(path, obj):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False, default=str)
    os.replace(tmp, path)


def read_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def write_text(path, text):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def parse_date(s):
    return dt.date.fromisoformat(s[:10])


def days_between(a, b):
    return (parse_date(b) - parse_date(a)).days


def today():
    return dt.date.today().isoformat()


def accn_folder(accn):
    return accn.replace("-", "")


def filing_index_url(cik, accn):
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn_folder(accn)}/{accn}-index.htm"


def filing_doc_url(cik, accn, doc):
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn_folder(accn)}/{doc}"


CURRENCY_SYMBOLS = {
    "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CNY": "CN¥", "TWD": "NT$", "KRW": "₩",
    "HKD": "HK$", "CAD": "C$", "AUD": "A$", "CHF": "CHF ", "INR": "₹", "SEK": "SEK ",
    "DKK": "DKK ", "NOK": "NOK ", "BRL": "R$", "MXN": "MX$", "ILS": "₪", "SGD": "S$",
}


def currency_symbol(code):
    return CURRENCY_SYMBOLS.get((code or "USD").upper(), (code or "") + " ")


def run_paths(run_dir):
    run_dir = os.path.abspath(run_dir)
    return {
        "run": run_dir,
        "data": os.path.join(run_dir, "data"),
        "notes": os.path.join(run_dir, "notes"),
        "parts": os.path.join(run_dir, "parts"),
        "build": os.path.join(run_dir, "build"),
        "run_json": os.path.join(run_dir, "run.json"),
    }


def update_run(run_dir, **fields):
    p = run_paths(run_dir)["run_json"]
    data = read_json(p, {}) or {}
    for k, v in fields.items():
        if isinstance(v, dict) and isinstance(data.get(k), dict):
            data[k].update(v)
        else:
            data[k] = v
    data["updated"] = dt.datetime.now().isoformat(timespec="seconds")
    write_json(p, data)
    return data


_SUFFIX = re.compile(r"(,?\s+(inc|incorporated|corp|corporation|co|company|ltd|limited|plc|nv|n\.v|sa|s\.a|ag|se|lp|llc|"
                     r"holdings?|group|/de|/md|/new)\.?)+\s*$", re.I)
_KEEP_LOWER = {"and", "of", "the", "for", "&"}


def display_name(name):
    """'MARVELL TECHNOLOGY, INC' -> 'Marvell Technology'; 'Credo Technology Group Holding Ltd' -> 'Credo Technology'."""
    if not name:
        return name
    n = re.sub(r"\s+", " ", str(name)).strip().rstrip(".")
    for _ in range(3):
        n = _SUFFIX.sub("", n).strip().rstrip(",")
    if n.isupper():
        words = []
        for w in n.split(" "):
            lw = w.lower()
            if lw in _KEEP_LOWER and words:
                words.append(lw)
            elif w.isalpha() and (len(w) <= 3 or (len(w) <= 5 and len(n.split(" ")) == 1)):
                words.append(w)          # likely an acronym (AMD, IBM, ASML)
            else:
                words.append(w.capitalize())
        n = " ".join(words)
    return n or name


class locked:
    """Exclusive lock around a read-modify-write of a shared file (analyst agents run in parallel)."""

    def __init__(self, path):
        self.lock_path = path + ".lock"

    def __enter__(self):
        os.makedirs(os.path.dirname(self.lock_path) or ".", exist_ok=True)
        self.fh = open(self.lock_path, "w")
        try:
            import fcntl
            fcntl.flock(self.fh, fcntl.LOCK_EX)
        except ImportError:  # Windows: no flock, runs unlocked
            pass
        return self

    def __exit__(self, *exc):
        try:
            import fcntl
            fcntl.flock(self.fh, fcntl.LOCK_UN)
        except ImportError:
            pass
        self.fh.close()
        return False
