"""cocotb lockstep bench for tt_mac_array vs the NumPy model (per-column dot products)."""
import os

import cocotb
import numpy as np
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

from tbutil import pack, unpack_signed

N = int(os.environ.get("ARRAY_N", "4"))
DW = int(os.environ.get("DATA_W", "8"))
AW = int(os.environ.get("ACC_W", "24"))


async def _reset(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst_n.value = 0
    dut.en.value = 0
    dut.w_load.value = 0
    dut.in_valid.value = 0
    dut.w_flat.value = 0
    dut.a_flat.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


def _load_weights(dut, W):
    # wmem[k][c] = W[c][k]  (array stores W transposed); flatten as (k*N + c)
    vals = [int(W[c][k]) for k in range(N) for c in range(N)]
    dut.w_flat.value = pack(vals, DW)


@cocotb.test()
async def test_array_single_tile(dut):
    """s_out[c] for column m must equal (W @ A)[c, m], bit-exact, over random tiles."""
    await _reset(dut)
    rng = np.random.default_rng(1)
    M = 6
    for trial in range(40):
        W = rng.integers(-128, 128, size=(N, N), dtype=np.int8)   # W[c][k] view
        A = rng.integers(-128, 128, size=(N, M), dtype=np.int8)   # A[k][m]
        _load_weights(dut, W)
        dut.w_load.value = 1
        await RisingEdge(dut.clk)
        dut.w_load.value = 0

        dut.en.value = 1
        produced = []
        m_in = 0
        for _ in range(M + N + 4):
            if m_in < M:
                dut.a_flat.value = pack([int(A[k][m_in]) for k in range(N)], DW)
                dut.in_valid.value = 1
                m_in += 1
            else:
                dut.in_valid.value = 0
                dut.a_flat.value = 0
            await RisingEdge(dut.clk)
            if int(dut.out_valid.value) == 1:
                produced.append(unpack_signed(int(dut.s_flat.value), N, AW))
        dut.en.value = 0

        exp = W.astype(np.int64) @ A.astype(np.int64)   # exp[c][m]
        assert len(produced) >= M, f"trial {trial}: {len(produced)} outputs < {M}"
        for m in range(M):
            for c in range(N):
                assert produced[m][c] == exp[c][m], (
                    f"trial {trial} col {m} row {c}: got {produced[m][c]} exp {exp[c][m]}")


@cocotb.test()
async def test_array_backpressure(dut):
    """Stalling en must not corrupt results (pipeline holds)."""
    await _reset(dut)
    rng = np.random.default_rng(7)
    W = rng.integers(-128, 128, size=(N, N), dtype=np.int8)
    A = rng.integers(-128, 128, size=(N, 3), dtype=np.int8)
    _load_weights(dut, W)
    dut.w_load.value = 1
    await RisingEdge(dut.clk)
    dut.w_load.value = 0

    produced = []
    m_in = 0
    M = 3
    for cyc in range(M + N + 12):
        stall = (cyc % 3 == 1)              # stall every 3rd cycle
        dut.en.value = 0 if stall else 1
        if not stall and m_in < M:
            dut.a_flat.value = pack([int(A[k][m_in]) for k in range(N)], DW)
            dut.in_valid.value = 1
            m_in += 1
        else:
            dut.in_valid.value = 0
        await RisingEdge(dut.clk)
        if int(dut.en.value) == 1 and int(dut.out_valid.value) == 1:
            produced.append(unpack_signed(int(dut.s_flat.value), N, AW))

    exp = W.astype(np.int64) @ A.astype(np.int64)
    assert len(produced) >= M, f"{len(produced)} outputs < {M}"
    for m in range(M):
        for c in range(N):
            assert produced[m][c] == exp[c][m], (
                f"col {m} row {c}: got {produced[m][c]} exp {exp[c][m]}")
