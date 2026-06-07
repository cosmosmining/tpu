#!/usr/bin/env python3
"""
metrics.py -- parse tool outputs into a summary and append one row to METRICS.md.

Phase 0: reads summary.json (written by smoke) and appends a dated, commit-stamped row.
Later phases extend the parsers (Yosys area/flops, OpenSTA WNS, coverage %, ATPG %).

Usage:
  scripts/metrics.py --from-summary summary.json [--phase N] [--note "..."]
  scripts/metrics.py --note "manual row" [--func-cov 97.3 --macs 1.2M --wns +0.18 ...]

METRICS.md is append-only: this script only ever appends a row.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METRICS = ROOT / "METRICS.md"
COLUMNS = ["date", "commit", "phase", "func_cov", "macs",
           "cells / area", "WNS", "util", "atpg", "notes"]


def git_short_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
            text=True, stderr=subprocess.DEVNULL).strip() or "n/a"
    except Exception:
        return "n/a"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-summary")
    ap.add_argument("--phase", default="")
    ap.add_argument("--func-cov", default="n/a")
    ap.add_argument("--macs", default="n/a")
    ap.add_argument("--area", default="n/a", dest="area")
    ap.add_argument("--wns", default="n/a")
    ap.add_argument("--util", default="n/a")
    ap.add_argument("--atpg", default="n/a")
    ap.add_argument("--note", default="")
    args = ap.parse_args()

    note = args.note
    phase = args.phase
    if args.from_summary:
        data = json.loads(Path(args.from_summary).read_text())
        phase = phase or str(data.get("phase", ""))
        res = data.get("results", {})
        status = "FAIL" if data.get("hard_fail") else "PASS"
        summarized = ", ".join(f"{k}:{v}" for k, v in res.items())
        note = note or f"`make {data.get('target','?')}` {status} ({summarized})"

    row = {
        "date": _dt.date.today().isoformat(),
        "commit": git_short_sha(),
        "phase": phase or "n/a",
        "func_cov": args.func_cov,
        "macs": args.macs,
        "cells / area": args.area,
        "WNS": args.wns,
        "util": args.util,
        "atpg": args.atpg,
        "notes": note or "n/a",
    }
    line = "| " + " | ".join(str(row[c]) for c in COLUMNS) + " |\n"

    if not METRICS.exists():
        raise SystemExit("METRICS.md not found")
    with METRICS.open("a") as f:
        f.write(line)
    print("appended METRICS row:", line.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
