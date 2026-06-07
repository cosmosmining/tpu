"""Shared cocotb driver for tensortile_core (used by tb_core and tb_regress)."""
import os

import cocotb
import numpy as np
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ReadOnly

from tbutil import pack

N = int(os.environ.get("ARRAY_N", "4"))
DW = int(os.environ.get("DATA_W", "8"))
AW = int(os.environ.get("ACC_W", "24"))
BW = 16
MAX_COLS = int(os.environ.get("MAX_COLS", "8"))


def rd_signed(sig, w):
    v = int(sig.value)
    return v - (1 << w) if v >= (1 << (w - 1)) else v


def dump(dut):
    g = lambda s: int(getattr(dut, s).value)
    return (f"busy={g('busy')} w_req={g('w_req')} col_ready={g('col_ready')} "
            f"out_valid={g('out_valid')} done={g('done')}")


async def wait_high(dut, name, maxc, ctx):
    c = 0
    while int(getattr(dut, name).value) == 0:
        await RisingEdge(dut.clk)
        c += 1
        assert c < maxc, f"timeout waiting {name} ({ctx}); {dump(dut)}"


async def reset(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    for s in ("start", "w_load", "b_load", "col_valid", "out_ready",
              "num_cols", "num_k_tiles", "shift", "relu_en", "bias_en",
              "w_flat", "b_flat", "a_flat"):
        getattr(dut, s).value = 0
    dut.rst_n.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


async def run_descriptor(dut, W, A, shift, bias, relu):
    """W: (N,K) int8 (W[c,k]); A: (K,M) int8; returns DUT output Y (N,M) int8."""
    K = W.shape[1]
    M = A.shape[1]
    assert K % N == 0 and M <= MAX_COLS
    nkt = K // N
    bias_en = bias is not None

    gc = 0
    while int(dut.busy.value) == 1:
        await RisingEdge(dut.clk)
        gc += 1
        assert gc < 200, f"core stuck busy before start; {dump(dut)}"

    if bias_en:
        dut.b_flat.value = pack([int(b) for b in bias], BW)
        dut.b_load.value = 1
        await RisingEdge(dut.clk)
        dut.b_load.value = 0

    dut.num_cols.value = M
    dut.num_k_tiles.value = nkt
    dut.shift.value = shift
    dut.relu_en.value = 1 if relu else 0
    dut.bias_en.value = 1 if bias_en else 0
    dut.start.value = 1
    await RisingEdge(dut.clk)
    dut.start.value = 0

    for kt in range(nkt):
        await wait_high(dut, "w_req", 200, f"kt={kt}")
        wv = [int(W[c][kt * N + k]) for k in range(N) for c in range(N)]
        dut.w_flat.value = pack(wv, DW)
        dut.w_load.value = 1
        await RisingEdge(dut.clk)
        dut.w_load.value = 0
        m = 0
        guard = 0
        while m < M:
            if int(dut.col_ready.value) == 1:
                dut.col_valid.value = 1
                dut.a_flat.value = pack([int(A[kt * N + k][m]) for k in range(N)], DW)
                await RisingEdge(dut.clk)
                m += 1
            else:
                dut.col_valid.value = 0
                await RisingEdge(dut.clk)
            guard += 1
            assert guard < M + 200, f"timeout streaming kt={kt} m={m}; {dump(dut)}"
        dut.col_valid.value = 0

    dut.out_ready.value = 1
    captured = []
    need = N * M
    timeout = need + 400
    while len(captured) < need and timeout > 0:
        await ReadOnly()
        if int(dut.out_valid.value) == 1:
            captured.append(rd_signed(dut.out_data, DW))
        await RisingEdge(dut.clk)
        timeout -= 1
    dut.out_ready.value = 0
    assert len(captured) == need, f"got {len(captured)}/{need} outputs; {dump(dut)}"

    Y = np.zeros((N, M), dtype=np.int64)
    for m in range(M):
        for c in range(N):
            Y[c][m] = captured[m * N + c]
    return Y
