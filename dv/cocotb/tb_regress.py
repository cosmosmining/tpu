"""
tb_regress.py -- Phase-3 constrained-random regression for tensortile_core.

Drives >= REGRESS_MACS (default 1,000,000) MAC operations across random shapes/data plus directed
adversarial cases (saturation extremes, most-negative operands, rounding ties), every descriptor
checked bit-exact vs the NumPy model. Tracks a functional-coverage model mapped to VPLAN and
writes a coverage report; gate requires zero mismatches and >= 95% functional coverage.
"""
import os

import cocotb
import numpy as np

from coreio import reset, run_descriptor, N, MAX_COLS
from model import gemm_ref as g

TARGET_MACS = int(os.environ.get("REGRESS_MACS", "1000000"))
COV_OUT = os.environ.get("COV_OUT", "coverage_phase3.md")

ALL_BINS = [
    "shift_zero", "shift_small", "shift_large",          # F-RND/req
    "relu_on", "relu_off",                                # F-RELU
    "bias_off", "bias_on", "bias_pos", "bias_neg",        # F-BIAS
    "op_neg128_w", "op_neg128_a", "product_max",          # F-NEG
    "sat_high", "sat_low",                                # F-SAT
    "tie_pos", "tie_neg", "nontie",                       # F-RND
    "kacc_1", "kacc_2_4", "kacc_5plus",                   # F-KACC
    "M_1", "M_mid", "M_max",                              # shapes
    "out_pos", "out_neg", "out_zero",                     # output range
]


def classify(W, A, shift, bias, relu):
    """Return the set of coverage bins this descriptor exercises (computed from the model)."""
    b = set()
    K, M = W.shape[1], A.shape[1]
    nkt = K // N
    b.add("shift_zero" if shift == 0 else ("shift_large" if shift >= 16 else "shift_small"))
    b.add("relu_on" if relu else "relu_off")
    if bias is None:
        b.add("bias_off")
    else:
        b.add("bias_on")
        if (np.asarray(bias) > 0).any(): b.add("bias_pos")
        if (np.asarray(bias) < 0).any(): b.add("bias_neg")
    if (W == -128).any(): b.add("op_neg128_w")
    if (A == -128).any(): b.add("op_neg128_a")
    for k in range(K):
        if (W[:, k] == -128).any() and (A[k, :] == -128).any():
            b.add("product_max"); break
    b.add("kacc_1" if nkt == 1 else ("kacc_2_4" if nkt <= 4 else "kacc_5plus"))
    b.add("M_1" if M == 1 else ("M_max" if M == MAX_COLS else "M_mid"))

    acc = g.matmul_acc(W, A).astype(np.int64)
    t = acc + (np.asarray(bias, np.int64)[:, None] if bias is not None else 0)
    r = t if shift == 0 else (t + (1 << (shift - 1))) >> shift
    lo = 0 if relu else g.INT8_MIN
    if (r > g.INT8_MAX).any(): b.add("sat_high")
    if (r < lo).any(): b.add("sat_low")
    if shift > 0:
        frac = t & ((1 << shift) - 1)
        half = 1 << (shift - 1)
        if ((frac == half) & (t >= 0)).any(): b.add("tie_pos")
        if ((frac == half) & (t < 0)).any(): b.add("tie_neg")
        if (frac != half).any(): b.add("nontie")
    else:
        b.add("nontie")
    y = np.clip(r, lo, g.INT8_MAX)
    if (y > 0).any(): b.add("out_pos")
    if (y < 0).any(): b.add("out_neg")
    if (y == 0).any(): b.add("out_zero")
    return b


def _onehot_col(value, k, m):
    """W with W[c,k0]=1 else 0; helper to craft exact accumulators."""


def directed_cases():
    """Adversarial descriptors that pin the rare coverage bins."""
    cases = []
    # 1) most-negative everywhere -> product_max, op_neg128, sat_high
    cases.append((np.full((N, 2 * N), -128, np.int8), np.full((2 * N, 4), -128, np.int8),
                  10, None, False))
    # 2) large negative accumulator -> sat_low (relu off)
    cases.append((np.full((N, N), 127, np.int8), np.full((N, 3), -128, np.int8), 2, None, False))
    # 3) positive rounding tie: acc=2, shift=2 (2 mod 4 == 2)
    Wp = np.zeros((N, N), np.int8); Wp[:, 0] = 1
    Ap = np.zeros((N, 1), np.int8); Ap[0, 0] = 2
    cases.append((Wp, Ap, 2, None, False))
    # 4) negative rounding tie + out_zero: acc=-2, shift=2
    An = np.zeros((N, 1), np.int8); An[0, 0] = -2
    cases.append((Wp, An, 2, None, False))
    # 5) relu with negatives -> out_zero via relu
    rng = np.random.default_rng(99)
    cases.append((rng.integers(-128, 128, (N, N), np.int8),
                  rng.integers(-128, 128, (N, 6), np.int8), 3, None, True))
    # 6) bias positive & negative, shift large
    bias = np.array([30000, -30000] + [0] * (N - 2), np.int64)[:N]
    cases.append((rng.integers(-8, 8, (N, N), np.int8),
                  rng.integers(-8, 8, (N, MAX_COLS), np.int8), 18, bias, False))
    # 7) kacc_5plus, M_max
    cases.append((rng.integers(-128, 128, (N, 6 * N), np.int8),
                  rng.integers(-128, 128, (6 * N, MAX_COLS), np.int8), 7, None, False))
    return cases


@cocotb.test()
async def test_regression(dut):
    await reset(dut)
    rng = np.random.default_rng(2024)
    covered = set()
    mismatches = 0
    total_macs = 0
    ndesc = 0

    async def do(W, A, shift, bias, relu):
        nonlocal mismatches, total_macs, ndesc
        got = await run_descriptor(dut, W, A, shift=shift, bias=bias, relu=relu)
        exp = g.quant_gemm(W, A, shift=shift, bias=bias, relu=relu)
        if not np.array_equal(got, exp):
            mismatches += 1
            assert False, (f"MISMATCH desc#{ndesc} shift={shift} relu={relu} "
                           f"bias={'y' if bias is not None else 'n'}\n got {got}\n exp {exp}")
        covered.update(classify(W, A, shift, bias, relu))
        total_macs += N * W.shape[1] * A.shape[1]
        ndesc += 1

    for (W, A, s, b, r) in directed_cases():
        await do(W, A, s, b, r)

    while total_macs < TARGET_MACS and ndesc < 200000:
        nkt = int(rng.integers(1, 9))
        M = int(rng.integers(1, MAX_COLS + 1))
        K = nkt * N
        shift = int(rng.integers(0, 20))
        relu = bool(rng.integers(0, 2))
        use_bias = bool(rng.integers(0, 2))
        # occasionally bias toward extreme operands for adversarial coverage
        if rng.integers(0, 4) == 0:
            W = rng.choice([-128, -1, 0, 1, 127], size=(N, K)).astype(np.int8)
            A = rng.choice([-128, -1, 0, 1, 127], size=(K, M)).astype(np.int8)
        else:
            W = rng.integers(-128, 128, size=(N, K), dtype=np.int8)
            A = rng.integers(-128, 128, size=(K, M), dtype=np.int8)
        bias = rng.integers(g.BIAS_MIN, g.BIAS_MAX + 1, size=N) if use_bias else None
        await do(W, A, shift, bias, relu)

    hit = [x for x in ALL_BINS if x in covered]
    miss = [x for x in ALL_BINS if x not in covered]
    cov_pct = 100.0 * len(hit) / len(ALL_BINS)

    report = [
        "# Phase 3 — Functional Coverage Report (tensortile_core)\n",
        f"- descriptors: **{ndesc}**",
        f"- MAC operations: **{total_macs:,}** (target {TARGET_MACS:,})",
        f"- mismatches vs model: **{mismatches}**",
        f"- functional coverage: **{cov_pct:.1f}%** ({len(hit)}/{len(ALL_BINS)} bins)\n",
        "| bin | hit |", "|-----|-----|",
    ]
    for x in ALL_BINS:
        report.append(f"| {x} | {'YES' if x in covered else 'no'} |")
    if miss:
        report.append(f"\n_misses: {', '.join(miss)}_")
    try:
        with open(COV_OUT, "w") as f:
            f.write("\n".join(report) + "\n")
    except OSError:
        pass

    dut._log.info(f"REGRESS: {ndesc} descriptors, {total_macs:,} MACs, "
                  f"{mismatches} mismatches, coverage {cov_pct:.1f}% ({len(hit)}/{len(ALL_BINS)})")
    assert mismatches == 0, f"{mismatches} mismatches"
    assert total_macs >= TARGET_MACS, f"only {total_macs} MACs (< {TARGET_MACS})"
    assert cov_pct >= 95.0, f"coverage {cov_pct:.1f}% < 95% (misses: {miss})"
