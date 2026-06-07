"""cocotb bench for tt_requant vs model.gemm_ref.requant_scalar (combinational DUT)."""
import os

import cocotb
import numpy as np
from cocotb.triggers import Timer

from model import gemm_ref as g

ACC_W = int(os.environ.get("ACC_W", "24"))
DW = int(os.environ.get("DATA_W", "8"))
BW = 16


def _u(v, w):
    return v & ((1 << w) - 1)


def _rd_signed(sig, w):
    v = int(sig.value)
    return v - (1 << w) if v >= (1 << (w - 1)) else v


async def _apply(dut, acc, bias, bias_en, shift, relu):
    dut.acc.value = _u(acc, ACC_W)
    dut.bias.value = _u(bias, BW)
    dut.bias_en.value = bias_en
    dut.shift.value = shift
    dut.relu_en.value = relu
    await Timer(1, unit="ns")
    return _rd_signed(dut.y, DW)


@cocotb.test()
async def test_requant_spec_examples(dut):
    # (acc, bias, bias_en, shift, relu, expected) -- the SPEC s2.4 table.
    cases = [
        (5, 0, 0, 0, 0, 5),
        (6, 0, 0, 2, 0, 2),
        (5, 0, 0, 2, 0, 1),
        (7, 0, 0, 2, 0, 2),
        (-6, 0, 0, 2, 0, -1),
        (-7, 0, 0, 2, 0, -2),
        (-2, 0, 0, 2, 0, 0),
        (300, 0, 0, 0, 0, 127),
        (-300, 0, 0, 0, 0, -128),
        (-300, 0, 0, 0, 1, 0),
        (-5, 0, 0, 0, 1, 0),
        (100, 27, 1, 0, 0, 127),
        (100, 28, 1, 0, 0, 127),
        (65536, 0, 0, 9, 0, 127),
    ]
    for acc, bias, ben, shift, relu, exp in cases:
        got = await _apply(dut, acc, bias, ben, shift, relu)
        assert got == exp, f"acc={acc} bias={bias} en={ben} s={shift} relu={relu}: {got}!={exp}"


@cocotb.test()
async def test_requant_random_vs_model(dut):
    rng = np.random.default_rng(3)
    for _ in range(2000):
        acc = int(rng.integers(g.ACC_MIN, g.ACC_MAX + 1))
        ben = int(rng.integers(0, 2))
        bias = int(rng.integers(g.BIAS_MIN, g.BIAS_MAX + 1)) if ben else 0
        shift = int(rng.integers(0, 21))
        relu = int(rng.integers(0, 2))
        got = await _apply(dut, acc, bias, ben, shift, relu)
        exp = g.requant_scalar(acc, shift, bias=bias, relu=bool(relu))
        assert got == exp, f"acc={acc} bias={bias} en={ben} s={shift} relu={relu}: {got}!={exp}"
