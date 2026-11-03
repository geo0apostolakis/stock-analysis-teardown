#!/usr/bin/env python3
"""Record or show pipeline progress in run.json, so an interrupted run resumes where it stopped.

usage: phase.py RUN_DIR                      show every phase and its status
       phase.py RUN_DIR NAME STATUS [NOTE]   e.g. phase.py RUN part2-financials done
Phases: resolve, data-room, part1-business, part1-strategy, part2-financials, part3-competition,
part4-valuation, verifier-editor, designer. Status: running, done, failed.
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import locked, read_json, run_paths, update_run  # noqa: E402

PHASES = ["resolve", "data-room", "part1-business", "part1-strategy", "part2-financials", "part3-competition",
          "part4-valuation", "verifier-editor", "designer"]


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    run_dir = sys.argv[1]
    paths = run_paths(run_dir)
    if len(sys.argv) == 2:
        run = read_json(paths["run_json"], {}) or {}
        ph = run.get("phases", {})
        for p in PHASES:
            v = ph.get(p, "pending")
            print(f"{p:18s} {v if isinstance(v, str) else v.get('status')}")
        return
    name, status = sys.argv[2], sys.argv[3]
    note = " ".join(sys.argv[4:])
    with locked(paths["run_json"]):
        update_run(run_dir, phases={name: status}, **({"phase_notes": {name: note}} if note else {}),
                   updated=dt.datetime.now().isoformat(timespec="seconds"))
    print(f"{name}: {status}")


if __name__ == "__main__":
    main()
