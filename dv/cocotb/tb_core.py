"""cocotb lockstep bench for tensortile_core vs model.gemm_ref (full GEMM + K-tiling + bias/ReLU)."""
import cocotb
import numpy as np

from coreio import reset, run_descriptor, N, MAX_COLS
from model import gemm_ref as g


@cocotb.test()
async def test_core_single_tile(dut):
    await reset(dut)
    rng = np.random.default_rng(10)
    for M in (1, 3, MAX_COLS):
        W = rng.integers(-128, 128, size=(N, N), dtype=np.int8)
        A = rng.integers(-128, 128, size=(N, M), dtype=np.int8)
        got = await run_descriptor(dut, W, A, shift=4, bias=None, relu=False)
        exp = g.quant_gemm(W, A, shift=4, bias=None, relu=False)
        assert np.array_equal(got, exp), f"M={M}\n got {got}\n exp {exp}"


@cocotb.test()
async def test_core_ktiling(dut):
    await reset(dut)
    rng = np.random.default_rng(11)
    for nkt in (2, 4):
        K, M = nkt * N, 4
        W = rng.integers(-128, 128, size=(N, K), dtype=np.int8)
        A = rng.integers(-128, 128, size=(K, M), dtype=np.int8)
        got = await run_descriptor(dut, W, A, shift=6, bias=None, relu=False)
        exp = g.quant_gemm(W, A, shift=6, bias=None, relu=False)
        assert np.array_equal(got, exp), f"nkt={nkt}\n got {got}\n exp {exp}"


@cocotb.test()
async def test_core_bias_relu(dut):
    await reset(dut)
    rng = np.random.default_rng(12)
    K, M = 2 * N, min(5, MAX_COLS)
    W = rng.integers(-128, 128, size=(N, K), dtype=np.int8)
    A = rng.integers(-128, 128, size=(K, M), dtype=np.int8)
    bias = rng.integers(g.BIAS_MIN, g.BIAS_MAX + 1, size=N)
    for relu in (False, True):
        got = await run_descriptor(dut, W, A, shift=5, bias=bias, relu=relu)
        exp = g.quant_gemm(W, A, shift=5, bias=bias, relu=relu)
        assert np.array_equal(got, exp), f"relu={relu}\n got {got}\n exp {exp}"


@cocotb.test()
async def test_core_random(dut):
    await reset(dut)
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
