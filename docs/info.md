<!---

This file is the datasheet for the TensorTile Tiny Tapeout project. The TT GDS
action renders it into the project page. Full engineering detail lives in
docs/SPEC.md, docs/INTEGRATION.md, and docs/VPLAN.md.

-->

## How it works

TensorTile is a **weight-stationary INT8 systolic GEMM accelerator** — a small TPU-v1-style
matrix-multiply tile with on-chip per-tensor requantization.

- A **4×4 array of MAC processing elements** holds an INT8 weight tile stationary. Activation
  columns stream in with row skew; INT8×INT8 products accumulate down 24-bit column accumulators.
- **Multi-tile K-accumulation:** the host streams successive K-tiles for one descriptor and the
  column accumulators sum across them, so arbitrarily large GEMMs can be tiled in software.
- Each output passes through **bias → arithmetic requant shift → saturating ReLU** back to INT8,
  then out through an output FIFO.
- The whole thing is driven over **SPI**: an SPI→APB bridge writes a CSR / descriptor-queue block
  (control, descriptor fields `num_cols / num_k_tiles / shift / relu_en / bias_en`, status, and
  performance counters), and streams weights/activations in, results out.
- Fully parametric (`ARRAY_N`, `DATA_W`, `ACC_W`, `MAX_COLS`). **Frozen tapeout point:** ARRAY_N=4,
  DATA_W=8, ACC_W=24, **MAX_COLS=4** (batch up to 4 activation columns per tile), single 50 MHz clock.
- **Peak compute:** 16 MAC/cycle → 0.8 GMAC/s at 50 MHz. All storage is flops (no SRAM macros).

The arithmetic is **bit-exact** to a NumPy golden model: RTL = model on every output, verified by a
1M-MAC constrained-random regression (0 mismatches) and SymbiYosys formal proofs of the FIFO and core.

## How to test

The flagship demo is a **2-layer quantized MLP classifying 8×8 MNIST digits**, bit-exact between
silicon and NumPy.

1. Hold the design in reset (active-low), supply a 50 MHz clock.
2. Over SPI, write the control CSRs and push a descriptor (`num_cols`, `num_k_tiles`, `shift`,
   `relu_en`, `bias_en`) — see `docs/INTEGRATION.md` for the CSR map and host tiling protocol.
3. Stream the per-K-tile weight matrix (pulse `w_load`), the bias vector once, then the activation
   columns; read INT8 results back over SPI in column-major order (column outer, row inner).
4. The provided RP2040 firmware (`fw/`) and the compiler (`compiler/`) turn a quantized MLP
   (`.npz`/ONNX) into tiled descriptors + data streams and run the MNIST demo end to end.
5. Status bits `busy` / `done` (and an `IRQ`) are exposed on the output pins for polling.

The committed cocotb benches (`dv/cocotb/`) reproduce the lockstep checks against the model; the
gate-level netlist can be exercised with the same full-chip SPI sequence.

## External hardware

None required. A microcontroller (e.g. the RP2040 on the Tiny Tapeout carrier board) drives the
SPI pins to stream weights/activations and read back results; firmware is provided in `fw/`.
