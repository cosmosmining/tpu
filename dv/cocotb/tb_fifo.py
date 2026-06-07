"""cocotb bench for tt_fifo vs a Python reference queue (random push/pop, full/empty/count)."""
import os
from collections import deque

import cocotb
import numpy as np
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ReadOnly

WIDTH = int(os.environ.get("FIFO_WIDTH", "8"))
DEPTH = int(os.environ.get("FIFO_DEPTH", "8"))


async def _reset(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.wr_en.value = 0
    dut.rd_en.value = 0
    dut.wr_data.value = 0
    dut.rst_n.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


@cocotb.test()
async def test_fifo_random(dut):
    await _reset(dut)
    rng = np.random.default_rng(5)
    model = deque()
    mask = (1 << WIDTH) - 1
    for _ in range(5000):
        full = (len(model) == DEPTH)
        empty = (len(model) == 0)
        do_wr = bool(rng.integers(0, 2)) and not full
        do_rd = bool(rng.integers(0, 2)) and not empty
        wdata = int(rng.integers(0, mask + 1))

        dut.wr_en.value = 1 if do_wr else 0
        dut.rd_en.value = 1 if do_rd else 0
        dut.wr_data.value = wdata

        await ReadOnly()  # sample combinational outputs against the model (pre-edge state)
        assert int(dut.count.value) == len(model), f"count {int(dut.count.value)} != {len(model)}"
        assert int(dut.full.value) == int(full)
        assert int(dut.empty.value) == int(empty)
        if not empty:
            assert int(dut.rd_data.value) == model[0], f"head {int(dut.rd_data.value)} != {model[0]}"

        await RisingEdge(dut.clk)  # apply the drives
        if do_rd:
            model.popleft()
        if do_wr:
            model.append(wdata & mask)
