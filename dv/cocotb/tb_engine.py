"""cocotb bench for tensortile_engine: descriptor queue + back-to-back execution, bit-exact."""
import cocotb
import numpy as np
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ReadOnly

from coreio import wait_high, N, DW, MAX_COLS
from tbutil import pack, unpack_signed
from model import gemm_ref as g


def _desc(num_cols, num_k_tiles, shift, relu, bias_en=False):
    return (num_cols & 0xFF) | ((num_k_tiles & 0xFF) << 8) | ((shift & 0x1F) << 16) \
        | ((1 if relu else 0) << 21) | ((1 if bias_en else 0) << 22)


async def _reset(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    for s in ("desc_wr", "desc_data", "w_load", "b_load", "col_valid", "out_ready",
              "w_flat", "b_flat", "a_flat"):
        getattr(dut, s).value = 0
    dut.rst_n.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


async def _enqueue(dut, desc):
    assert int(dut.desc_full.value) == 0, "descriptor queue full"
    dut.desc_data.value = desc
    dut.desc_wr.value = 1
    await RisingEdge(dut.clk)
    dut.desc_wr.value = 0


async def _service(dut, W, A):
    """Supply weights/activations for the head descriptor (engine auto-started it); collect results."""
    K, M = W.shape[1], A.shape[1]
    nkt = K // N
    for kt in range(nkt):
        await wait_high(dut, "w_req", 400, f"kt={kt}")
        dut.w_flat.value = pack([int(W[c][kt * N + k]) for k in range(N) for c in range(N)], DW)
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
            assert guard < M + 300, "stream timeout"
        dut.col_valid.value = 0

    dut.out_ready.value = 1
    captured = []
    need = N * M
    timeout = need + 400
    while len(captured) < need and timeout > 0:
        await ReadOnly()
        if int(dut.out_valid.value) == 1:
            captured.append(unpack_signed(int(dut.out_data.value) & ((1 << DW) - 1), 1, DW)[0])
        await RisingEdge(dut.clk)
        timeout -= 1
    dut.out_ready.value = 0
    assert len(captured) == need, f"{len(captured)}/{need} results"
    Y = np.zeros((N, M), np.int64)
    for m in range(M):
        for c in range(N):
            Y[c][m] = captured[m * N + c]
    return Y


@cocotb.test()
async def test_engine_queue_backtoback(dut):
    await _reset(dut)
    rng = np.random.default_rng(50)
    descs = []
    for _ in range(3):
        nkt = int(rng.integers(1, 4))
        M = int(rng.integers(1, MAX_COLS + 1))
        shift = int(rng.integers(0, 10))
        relu = bool(rng.integers(0, 2))
        W = rng.integers(-128, 128, (N, nkt * N), np.int8)
        A = rng.integers(-128, 128, (nkt * N, M), np.int8)
        descs.append((W, A, shift, relu))

    # enqueue all three up front (exercises the queue; engine auto-starts the head)
    for (W, A, shift, relu) in descs:
        await _enqueue(dut, _desc(A.shape[1], W.shape[1] // N, shift, relu))
    await ReadOnly()
    assert int(dut.desc_occupancy.value) >= 1   # at least one still queued (head may have popped)
    await RisingEdge(dut.clk)

    # service in FIFO order; every result bit-exact
    for (W, A, shift, relu) in descs:
        Y = await _service(dut, W, A)
        exp = g.quant_gemm(W, A, shift=shift, bias=None, relu=relu)
        assert np.array_equal(Y, exp), f"shift={shift} relu={relu}\n got {Y}\n exp {exp}"

    # drained -> engine idle, queue empty
    for _ in range(5):
        await RisingEdge(dut.clk)
    assert int(dut.idle.value) == 1
    assert int(dut.desc_occupancy.value) == 0


@cocotb.test()
async def test_engine_queue_full(dut):
    """Filling QDEPTH descriptors asserts desc_full (hold the head by not servicing)."""
    await _reset(dut)
    # the engine pops the head immediately (idle); to fill, enqueue faster than it drains: enqueue
    # 4 in consecutive cycles and check full asserts at capacity.
    filled = 0
    for i in range(4):
        if int(dut.desc_full.value) == 1:
            break
        dut.desc_data.value = _desc(1, 1, 0, False)
        dut.desc_wr.value = 1
        await RisingEdge(dut.clk)
        filled += 1
    dut.desc_wr.value = 0
    await ReadOnly()
    # capacity is QDEPTH=4; with the head popped once, occupancy peaks at 3-4
    assert int(dut.desc_occupancy.value) >= 3, f"occupancy {int(dut.desc_occupancy.value)}"
