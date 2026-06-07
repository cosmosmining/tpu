#!/usr/bin/env python3
"""
smoke.py -- the Phase-0 gate. Fast "is the repo wired up correctly?" check.

Passes on a clean clone. Each sub-check either RUNS (tool present) or is loudly marked
SKIP->CI (tool absent locally but covered by CI) -- never a silent skip. Exits non-zero only
if a sub-check that *could* run FAILED.

Checks:
  1. Python + numpy import, and a known-answer INT8 matmul (proves the arithmetic env).
     NOTE: this is plain integer matmul, NOT the chip's requant arithmetic -- the bit-exact
     golden model is defined in Phase 1 after SPEC freeze, so smoke must not pre-empt it.
  2. verilator --lint-only on the top module (if verilator present).
  3. iverilog compile of the top module (if iverilog present).

Writes summary.json for scripts/metrics.py.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOP = ROOT / "rtl" / "tt_top" / "tt_um_tensortile.v"
RESULTS: dict[str, str] = {}
HARD_FAIL = False


def record(name: str, status: str, detail: str = "") -> None:
    RESULTS[name] = status
    mark = {"RUN-OK": "[ OK ]", "FAIL": "[FAIL]", "SKIP->CI": "[SKIP]"}.get(status, status)
    line = f"  {mark} {name}"
    if detail:
        line += f" -- {detail}"
    print(line)


def have(tool: str) -> bool:
    return shutil.which(tool) is not None


def check_numpy() -> None:
    global HARD_FAIL
    try:
        import numpy as np
    except Exception as e:  # pragma: no cover
        record("python/numpy import", "FAIL", repr(e))
        HARD_FAIL = True
        return
    record("python/numpy import", "RUN-OK", f"numpy {np.__version__}")

    # Known-answer INT8 -> INT32 matmul (plain integer accumulation; not requant).
    a = np.array([[1, 2, 3], [-4, 5, -6]], dtype=np.int8)        # 2x3
    b = np.array([[7, -8], [9, 10], [-11, 12]], dtype=np.int8)   # 3x2
    got = a.astype(np.int32) @ b.astype(np.int32)
    # Hand-computed expected:
    #   [ 1*7 + 2*9 + 3*-11 ,  1*-8 + 2*10 + 3*12 ] = [ -8 , 48 ]
    #   [-4*7 + 5*9 + -6*-11 , -4*-8 + 5*10 + -6*12] = [ 83 , 10 ]
    expect = np.array([[-8, 48], [83, 10]], dtype=np.int32)
    if np.array_equal(got, expect):
        record("known-answer INT8 matmul", "RUN-OK", "2x3 @ 3x2 == expected")
    else:
        record("known-answer INT8 matmul", "FAIL", f"got {got.tolist()} != {expect.tolist()}")
        HARD_FAIL = True


def run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def check_verilator() -> None:
    global HARD_FAIL
    if not have("verilator"):
        record("verilator lint", "SKIP->CI", "verilator not installed locally")
        return
    rc, out = run(["verilator", "--lint-only", "-Wall", "--top-module",
                   "tt_um_tensortile", str(TOP)])
    if rc == 0:
        record("verilator lint", "RUN-OK", "tt_um_tensortile -Wall clean")
    else:
        record("verilator lint", "FAIL", out.splitlines()[-1] if out else f"rc={rc}")
        HARD_FAIL = True


def check_iverilog() -> None:
    global HARD_FAIL
    if not have("iverilog"):
        record("iverilog compile", "SKIP->CI", "iverilog not installed locally")
        return
    out_vvp = ROOT / "build" / "tt_stub.vvp"
    out_vvp.parent.mkdir(exist_ok=True)
    rc, out = run(["iverilog", "-g2012", "-o", str(out_vvp), str(TOP)])
    if rc == 0:
        record("iverilog compile", "RUN-OK", "tt_um_tensortile compiled")
    else:
        record("iverilog compile", "FAIL", out.splitlines()[-1] if out else f"rc={rc}")
        HARD_FAIL = True


def main() -> int:
    print("=== TensorTile smoke (Phase 0 gate) ===")
    if not TOP.exists():
        record("top module present", "FAIL", str(TOP))
        return 2
    check_numpy()
    check_verilator()
    check_iverilog()

    summary = {
        "phase": 0,
        "target": "smoke",
        "results": RESULTS,
        "hard_fail": HARD_FAIL,
    }
    (ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    print("---")
    skipped = [k for k, v in RESULTS.items() if v == "SKIP->CI"]
    if skipped:
        print(f"  {len(skipped)} check(s) SKIP->CI (covered in CI): {', '.join(skipped)}")
    if HARD_FAIL:
        print("SMOKE: FAIL")
        return 1
    print("SMOKE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
