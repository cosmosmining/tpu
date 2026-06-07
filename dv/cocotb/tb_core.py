"""cocotb lockstep bench for tensortile_core vs model.gemm_ref (full GEMM + K-tiling + bias/ReLU)."""
import os

import cocotb
import numpy as np
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ReadOnly

from tbutil import pack
from model import gemm_ref as g

N = int(os.environ.get("ARRAY_N", "4"))
DW = int(os.environ.get("DATA_W", "8"))
AW = int(os.environ.get("ACC_W", "24"))
BW = 16
MAX_COLS = int(os.environ.get("MAX_COLS", "8"))


def _rd_signed(sig, w):
    v = int(sig.value)
    return v - (1 << w) if v >= (1 << (w - 1)) else v


def _dump(dut):
    g = lambda s: int(getattr(dut, s).value)
    return (f"busy={g('busy')} w_req={g('w_req')} col_ready={g('col_ready')} "
            f"out_valid={g('out_valid')} done={g('done')}")


async def _wait_high(dut, name, maxc, ctx):
    c = 0
    while int(getattr(dut, name).value) == 0:
        await RisingEdge(dut.clk)
        c += 1
        assert c < maxc, f"timeout waiting {name} ({ctx}); {_dump(dut)}"


async def _reset(dut):
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
    """W: (N, K) int8 (W[c,k]); A: (K, M) int8; returns captured Y (N, M) int8 from the DUT."""
    K = W.shape[1]
    M = A.shape[1]
    assert K % N == 0 and M <= MAX_COLS
    nkt = K // N
    bias_en = bias is not None

    # ensure the core is idle before programming a new descriptor
    gc = 0
    while int(dut.busy.value) == 1:
        await RisingEdge(dut.clk)
        gc += 1
        assert gc < 50, f"core stuck busy before start; {_dump(dut)}"

    # bias load
    if bias_en:
        dut.b_flat.value = pack([int(b) for b in bias], BW)
        dut.b_load.value = 1
        await RisingEdge(dut.clk)
        dut.b_load.value = 0

    # start with descriptor
    dut.num_cols.value = M
    dut.num_k_tiles.value = nkt
    dut.shift.value = shift
    dut.relu_en.value = 1 if relu else 0
    dut.bias_en.value = 1 if bias_en else 0
    dut.start.value = 1
    await RisingEdge(dut.clk)
    dut.start.value = 0

    # feed each K-tile when requested, then stream its columns
    for kt in range(nkt):
        await _wait_high(dut, "w_req", 100, f"kt={kt}")
        # wmem[k][c] = W[c][kt*N + k]; flat index (k*N + c)
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
            assert guard < M + 100, f"timeout streaming kt={kt} m={m}; {_dump(dut)}"
        dut.col_valid.value = 0

    # drain: capture N*M outputs in (col outer, row inner) order
    dut.out_ready.value = 1
    captured = []
    need = N * M
    timeout = need + 200
    while len(captured) < need and timeout > 0:
        await ReadOnly()
        if int(dut.out_valid.value) == 1:
            captured.append(_rd_signed(dut.out_data, DW))
        await RisingEdge(dut.clk)
        timeout -= 1
    dut.out_ready.value = 0
    assert len(captured) == need, f"got {len(captured)}/{need} outputs"

    Y = np.zeros((N, M), dtype=np.int64)
    for m in range(M):
        for c in range(N):
            Y[c][m] = captured[m * N + c]
    return Y


@cocotb.test()
async def test_core_single_tile(dut):
    await _reset(dut)
    rng = np.random.default_rng(10)
    for M in (1, 3, MAX_COLS):
        W = rng.integers(-128, 128, size=(N, N), dtype=np.int8)
        A = rng.integers(-128, 128, size=(N, M), dtype=np.int8)
        got = await run_descriptor(dut, W, A, shift=4, bias=None, relu=False)
        exp = g.quant_gemm(W, A, shift=4, bias=None, relu=False)
        assert np.array_equal(got, exp), f"M={M}\n got {got}\n exp {exp}"


@cocotb.test()
async def test_core_ktiling(dut):
    await _reset(dut)
    rng = np.random.default_rng(11)
    for nkt in (2, 4):
        K = nkt * N
        M = 4
        W = rng.integers(-128, 128, size=(N, K), dtype=np.int8)
        A = rng.integers(-128, 128, size=(K, M), dtype=np.int8)
        got = await run_descriptor(dut, W, A, shift=6, bias=None, relu=False)
        exp = g.quant_gemm(W, A, shift=6, bias=None, relu=False)
        assert np.array_equal(got, exp), f"nkt={nkt}\n got {got}\n exp {exp}"


@cocotb.test()
async def test_core_bias_relu(dut):
    await _reset(dut)
    rng = np.random.default_rng(12)
    K, M = 2 * N, 5
    W = rng.integers(-128, 128, size=(N, K), dtype=np.int8)
    A = rng.integers(-128, 128, size=(K, M), dtype=np.int8)
    bias = rng.integers(g.BIAS_MIN, g.BIAS_MAX + 1, size=N)
    for relu in (False, True):
        got = await run_descriptor(dut, W, A, shift=5, bias=bias, relu=relu)
        exp = g.quant_gemm(W, A, shift=5, bias=bias, relu=relu)
        assert np.array_equal(got, exp), f"relu={relu}\n got {got}\n exp {exp}"


@cocotb.test()
async def test_core_random(dut):
    await _reset(dut)
    rng = np.random.default_rng(123)
    for _ in range(25):
        nkt = int(rng.integers(1, 5))
        M = int(rng.integers(1, MAX_COLS + 1))
        K = nkt * N
        shift = int(rng.integers(0, 12))
        relu = bool(rng.integers(0, 2))
        use_bias = bool(rng.integers(0, 2))
        W = rng.integers(-128, 128, size=(N, K), dtype=np.int8)
        A = rng.integers(-128, 128, size=(K, M), dtype=np.int8)
        bias = rng.integers(g.BIAS_MIN, g.BIAS_MAX + 1, size=N) if use_bias else None
        got = await run_descriptor(dut, W, A, shift=shift, bias=bias, relu=relu)
        exp = g.quant_gemm(W, A, shift=shift, bias=bias, relu=relu)
        assert np.array_equal(got, exp), (
            f"nkt={nkt} M={M} shift={shift} relu={relu} bias={use_bias}\n got {got}\n exp {exp}")
