"""cocotb bench for tensortile_core performance counters (MACs, busy, stalls by cause)."""
import os

import cocotb
import numpy as np
from cocotb.triggers import RisingEdge

from coreio import reset, wait_high, N, DW
from tbutil import pack


async def _run(dut, W, A, shift, act_gap, bp_gap):
    """One descriptor with `act_gap` starvation cycles per K-tile and `bp_gap` backpressure cycles
    per drained element. Returns (busy, mac, stall_act, stall_bp) and the injected bp total."""
    K, M = W.shape[1], A.shape[1]
    nkt = K // N
    while int(dut.busy.value) == 1:
        await RisingEdge(dut.clk)
    dut.num_cols.value = M
    dut.num_k_tiles.value = nkt
    dut.shift.value = shift
    dut.relu_en.value = 0
    dut.bias_en.value = 0
    dut.start.value = 1
    await RisingEdge(dut.clk)
    dut.start.value = 0

    for kt in range(nkt):
        await wait_high(dut, "w_req", 200, f"kt={kt}")
        dut.w_load.value = 1
        dut.w_flat.value = pack([int(W[c][kt * N + k]) for k in range(N) for c in range(N)], DW)
        await RisingEdge(dut.clk)
        dut.w_load.value = 0
        for _ in range(act_gap):           # inject activation starvation
            dut.col_valid.value = 0
            await RisingEdge(dut.clk)
        m = 0
        while m < M:
            if int(dut.col_ready.value) == 1:
                dut.col_valid.value = 1
                dut.a_flat.value = pack([int(A[kt * N + k][m]) for k in range(N)], DW)
                await RisingEdge(dut.clk)
                m += 1
            else:
                dut.col_valid.value = 0
                await RisingEdge(dut.clk)
        dut.col_valid.value = 0

    need = N * M
    got = 0
    bp_total = 0
    while got < need:
        if int(dut.out_valid.value) == 1:
            for _ in range(bp_gap):        # inject result backpressure (out_valid stays high)
                dut.out_ready.value = 0
                await RisingEdge(dut.clk)
                bp_total += 1
            dut.out_ready.value = 1
            await RisingEdge(dut.clk)
            got += 1
        else:
            dut.out_ready.value = 1
            await RisingEdge(dut.clk)
    dut.out_ready.value = 0
    await RisingEdge(dut.clk)
    return (int(dut.perf_busy.value), int(dut.perf_mac.value),
            int(dut.perf_stall_act.value), int(dut.perf_stall_bp.value), bp_total)


@cocotb.test()
async def test_perf_mac_and_backpressure(dut):
    await reset(dut)
    rng = np.random.default_rng(40)
    M, nkt = 3, 2
    K = nkt * N
    W = rng.integers(-128, 128, (N, K), np.int8)
    A = rng.integers(-128, 128, (K, M), np.int8)

    # clean: out_ready always high during drain -> zero backpressure stalls
    busy, mac, sa0, sb0, _ = await _run(dut, W, A, shift=3, act_gap=0, bp_gap=0)
    assert mac == M * nkt * N * N, f"perf_mac {mac} != {M*nkt*N*N}"   # MACs = Nout*Ktotal*M
    assert sb0 == 0, f"clean backpressure stalls {sb0} != 0"
    assert busy > 0

    # inject 2 backpressure cycles per drained element -> ~2*need stalls (allow small edge slack)
    _, mac2, _, sb2, bp_inj = await _run(dut, W, A, shift=3, act_gap=0, bp_gap=2)
    assert mac2 == mac, "MAC count must be independent of backpressure"
    assert sb2 > 0 and abs(sb2 - 2 * (N * M)) <= 2, f"perf_stall_bp {sb2} (~{2*(N*M)} expected)"


@cocotb.test()
async def test_perf_starvation_monotonic(dut):
    await reset(dut)
    rng = np.random.default_rng(41)
    M, nkt = 2, 3
    K = nkt * N
    W = rng.integers(-128, 128, (N, K), np.int8)
    A = rng.integers(-128, 128, (K, M), np.int8)
    _, _, sa_none, _, _ = await _run(dut, W, A, shift=2, act_gap=0, bp_gap=0)
    _, _, sa_gap, _, _ = await _run(dut, W, A, shift=2, act_gap=4, bp_gap=0)
    # injecting 4 starvation cycles per K-tile must register (~4*nkt) and exceed the baseline
    assert sa_gap >= 4 * nkt - 2, f"starvation counter {sa_gap} below injected ~{4*nkt}"
    assert sa_gap > sa_none, f"starvation {sa_gap} not raised vs baseline {sa_none}"
