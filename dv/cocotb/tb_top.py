"""End-to-end cocotb bench for tt_um_tensortile: drive a GEMM over SPI, read results, vs model."""
import os

import cocotb
import numpy as np
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

from model import gemm_ref as g

N = int(os.environ.get("ARRAY_N", "4"))
SCLK_HALF = 4  # clk cycles per SCLK half-period (clk >> SCLK; oversampled slave)

# CSR addrs
A_STATUS, A_DNC, A_DNK, A_DCF, A_WDATA, A_ADATA, A_OUT, A_BDATA = \
    0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08


def _pins(dut, sclk, csn, mosi):
    dut.ui_in.value = (sclk & 1) | ((csn & 1) << 1) | ((mosi & 1) << 2)


async def _clkn(dut, n):
    for _ in range(n):
        await RisingEdge(dut.clk)


async def _xfer_byte(dut, byte, csn=0):
    """Clock one SPI byte (MSB first); sample MISO during each low phase. Returns the read byte."""
    rb = 0
    for i in range(8):
        bit = (byte >> (7 - i)) & 1
        _pins(dut, 0, csn, bit)          # SCLK low; slave holds MISO stable
        await _clkn(dut, SCLK_HALF)
        rb = (rb << 1) | (int(dut.uo_out.value) & 1)   # uo_out[0] = MISO
        _pins(dut, 1, csn, bit)          # SCLK high; slave samples MOSI on the (synced) rising edge
        await _clkn(dut, SCLK_HALF)
    return rb


async def spi_write(dut, addr, data_bytes):
    _pins(dut, 0, 1, 0)
    await _clkn(dut, 2)
    await _xfer_byte(dut, addr & 0x7F, csn=0)          # header: rw=0
    for b in data_bytes:
        await _xfer_byte(dut, b & 0xFF, csn=0)
    _pins(dut, 0, 1, 0)                                 # CSn high -> end frame
    await _clkn(dut, 3)


async def spi_read(dut, addr, n):
    _pins(dut, 0, 1, 0)
    await _clkn(dut, 2)
    await _xfer_byte(dut, 0x80 | (addr & 0x7F), csn=0)  # header: rw=1
    out = [await _xfer_byte(dut, 0x00, csn=0) for _ in range(n)]
    _pins(dut, 0, 1, 0)
    await _clkn(dut, 3)
    return out


async def _reset(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.ena.value = 1
    dut.uio_in.value = 0
    _pins(dut, 0, 1, 0)            # SCLK low, CSn high (idle)
    dut.rst_n.value = 0
    await _clkn(dut, 5)
    dut.rst_n.value = 1
    await _clkn(dut, 3)


def _s8(b):
    return b - 256 if b >= 128 else b


async def run_gemm_over_spi(dut, W, A, shift, relu):
    """Program + stream a GEMM (no bias) over SPI; return DUT results (N, M)."""
    K, M = W.shape[1], A.shape[1]
    nkt = K // N
    # enqueue descriptor (NC, NK, then CF commits)
    await spi_write(dut, A_DNC, [M])
    await spi_write(dut, A_DNK, [nkt])
    cf = (shift & 0x1F) | ((1 if relu else 0) << 5)
    await spi_write(dut, A_DCF, [cf])
    # stream per K-tile: 16 weight bytes (k*N+c order = W[c][k]) then M activation columns
    for kt in range(nkt):
        wbytes = [int(W[c][kt * N + k]) & 0xFF for k in range(N) for c in range(N)]
        await spi_write(dut, A_WDATA, wbytes)
        for m in range(M):
            await spi_write(dut, A_ADATA, [int(A[kt * N + k][m]) & 0xFF for k in range(N)])
    # wait for results, then read N*M bytes
    for _ in range(2000):
        st = (await spi_read(dut, A_STATUS, 1))[0]
        if st & 0x08:        # out_valid
            break
    raw = await spi_read(dut, A_OUT, N * M)
    Y = np.zeros((N, M), np.int64)
    for m in range(M):
        for c in range(N):
            Y[c][m] = _s8(raw[m * N + c])
    return Y


@cocotb.test()
async def test_top_spi_gemm(dut):
    await _reset(dut)
    rng = np.random.default_rng(70)
    for (nkt, M, shift, relu) in [(1, 1, 0, False), (1, 1, 3, False), (2, 1, 5, True)]:
        K = nkt * N
        W = rng.integers(-128, 128, (N, K), np.int8)
        A = rng.integers(-128, 128, (K, M), np.int8)
        got = await run_gemm_over_spi(dut, W, A, shift, relu)
        exp = g.quant_gemm(W, A, shift=shift, bias=None, relu=relu)
        assert np.array_equal(got, exp), f"nkt={nkt} M={M} shift={shift} relu={relu}\n got{got}\n exp{exp}"
