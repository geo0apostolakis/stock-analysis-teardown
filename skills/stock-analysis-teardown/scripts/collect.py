#!/usr/bin/env python3
"""One command for the whole numeric data layer (the data-room agent runs this first).

usage: collect.py RUN_DIR [--peers AVGO,CRDO,3661.TW] [--skip-filings] [--adr-ratio N]

  1. SEC statements, filing text, Form 4 insiders for the company      (fetch_sec.py)
  2. price, history, splits, beta, risk-free rate                      (fetch_market.py)
  3. every ratio                                                       (metrics.py compute)
  4. for each peer: SEC statements + price + ratios when it files with the SEC,
     price only otherwise (the agent then adds its numbers with peers.py manual)
  5. the peer table                                                    (peers.py build)
Prints a short report with warnings the agent must act on.
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _common import log, read_json, run_paths  # noqa: E402
from resolve import sec_lookup  # noqa: E402


def sh(*args):
    cmd = [sys.executable, *args]
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    if out:
        log(out)
    if r.returncode != 0:
        log(f"FAILED ({r.returncode}): {' '.join(args[:3])}")
    return r.returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--peers", default="")
    ap.add_argument("--skip-filings", action="store_true")
    ap.add_argument("--adr-ratio", default=None)
    args = ap.parse_args()
    run = read_json(run_paths(args.run_dir)["run_json"], {})
    ident = run.get("identity", {})
    data = run_paths(args.run_dir)["data"]

    if ident.get("sec_filer"):
        what = "facts" if args.skip_filings else "facts,filings,insiders"
        sh(os.path.join(HERE, "fetch_sec.py"), args.run_dir, "--what", what)
    else:
        log("Not an SEC filer: skipping SEC statements. Build statements from annual reports (see data-room brief).")
    sh(os.path.join(HERE, "fetch_market.py"), args.run_dir)
    if os.path.exists(os.path.join(data, "statements.json")):
        extra = ["--adr-ratio", args.adr_ratio] if args.adr_ratio else []
        sh(os.path.join(HERE, "metrics.py"), "compute", args.run_dir, *extra)

    for t in [p.strip().upper() for p in args.peers.split(",") if p.strip()]:
        dest = os.path.join(data, "peers", t)
        os.makedirs(dest, exist_ok=True)
        rec = sec_lookup(t)
        if rec:
            ok = sh(os.path.join(HERE, "fetch_sec.py"), args.run_dir, "--cik", str(rec["cik"]), "--ticker", t,
                    "--dest", dest, "--what", "facts")
            sh(os.path.join(HERE, "fetch_market.py"), args.run_dir, "--symbol", t.replace(".", "-"), "--dest", dest)
            if ok:
                sh(os.path.join(HERE, "metrics.py"), "compute", args.run_dir, "--dest", dest)
        else:
            sh(os.path.join(HERE, "fetch_market.py"), args.run_dir, "--symbol", t, "--dest", dest)
            log(f"{t} is not an SEC filer: price saved; add its financials with peers.py manual (with sources).")
    if os.path.exists(os.path.join(data, "metrics.json")):
        sh(os.path.join(HERE, "peers.py"), "build", args.run_dir)

    m = read_json(os.path.join(data, "metrics.json"), {}) or {}
    print("\n== data layer ready ==")
    print(f"metrics: {len(m.get('values', {}))} values; periods {m.get('meta', {}).get('display_periods')}")
    for w in m.get("meta", {}).get("warnings", []):
        print("WARNING:", w)
    print(f"read next: {os.path.join(data, 'financials.md')} and {os.path.join(data, 'filings', 'index.json')}")


if __name__ == "__main__":
    main()
