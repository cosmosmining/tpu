# INTEGRATION — TensorTile host & bring-up guide

> Phase-0 skeleton. The **host tiling protocol** is the centerpiece (Phase 8 datasheet). Filled
> across Phases 1/5/8. CSR map is generated from `regs/tensortile.rdl`.

## 1. Pin map (TT) — TODO (frozen with SPEC §8)
`ui_in[7:0]`, `uo_out[7:0]`, `uio_in[7:0]`, `uio_out[7:0]`, `uio_oe[7:0]`, `ena`, `clk`, `rst_n`.
Planned: SPI slave (SCLK/CSn/MOSI/MISO), IRQ out, test-mode scan muxed on `uio` under a
test-enable CSR bit.

## 2. CSR map — TODO (generated from regs/tensortile.rdl)
Control, descriptor regs / 4-deep queue (P1), status, IRQ enable/status, perf counters
(busy/MACs/util/stall-by-cause), test-enable.

## 3. Host tiling protocol — TODO (centerpiece)
How a host decomposes an arbitrary M×K×N GEMM into ARRAY_N tiles, weight preload order,
activation streaming with row skew, K-accumulation across tiles (accumulate-enable), requant
shift selection, result drain, and descriptor-queue pipelining so the core runs without
per-tile host intervention.

## 4. Streaming format — TODO
Weight stream (preload shift-chain order), activation stream (skew/packing), result stream
(output FIFO drain), all over SPI→APB3.

## 5. Bring-up guide — TODO (Phase 8)
Power-on, reset, CSR sanity, single-tile GEMM, K-accumulated GEMM, MNIST MLP demo, perf-counter
dump. RP2040 firmware in `fw/`.

## 6. Quantized-MLP demo flow — TODO
`compiler/` converts a quantized MLP (npz; ONNX optional) into tiled descriptors + data streams;
host streams them; silicon classifies 8×8 MNIST digits bit-exact vs `model/mlp_ref.py`.
