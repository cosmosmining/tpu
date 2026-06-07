# SPEC — TensorTile

> **FROZEN: NO.** This is a Phase-0 skeleton. Phase 1 fills every section and the operator
> *freezes* it before any design RTL is written. Bit-exactness is the product: the arithmetic
> defined here is law for the NumPy model, the RTL, and the silicon.

## 0. Scope & conventions
- TODO: notation, signedness conventions, bit-numbering, parameter table
  (`ARRAY_N`=4, `DATA_W`=8, `ACC_W`=24).

## 1. Function overview
Weight-stationary INT8 systolic GEMM tile with on-chip per-tensor requantization. Weights
preloaded and held in the PE array; activations stream in with row skew; partial sums flow down
column accumulators supporting multi-tile K-accumulation. Output path:
`{bias (P1) → requant shift → optional saturating ReLU} → output FIFO`.

## 2. Arithmetic definition (THE CONTRACT — Phase 1, must be unambiguous)
- TODO: **Accumulation** — width (`ACC_W`=24), signedness, overflow behavior. Worked example.
- TODO: **MAC** — INT8×INT8 product range, sign handling, most-negative operand (−128) case.
- TODO: **Bias add (P1)** — 16-bit signed, where it sits, saturation.
- TODO: **Requantization** — arithmetic right shift by a programmed amount; the **exact
  rounding rule** (e.g. round-half-up via `+ (1 << (shift-1))` then `>>`, or round-half-to-even
  — to be specified precisely), behavior at shift=0, and the saturation to INT8 `[-128, 127]`.
- TODO: **Saturating ReLU** — clamp lower bound to 0 when enabled; interaction with INT8 sat.
- TODO: **Worked numeric edge cases** — most-negative values, saturation at each stage,
  rounding ties (both directions), shift boundaries. Each with the exact expected output.

## 3. Microarchitecture / dataflow
- TODO: PE (weight reg, MAC, partial-sum pass-down), row skew, array composition, accumulator
  bank, requant unit, FIFOs. Pipeline depth and latency per stage.
- TODO: weight preload shift-chain protocol; ping-pong double buffer (P1).

## 4. Descriptor format
- TODO: fields — tile dims/counts (M/N/K tiling), accumulate-enable (K-tiling), requant shift
  amount, ReLU enable, bias-enable (P1). Bit layout. Descriptor command queue (P1, 4-deep).

## 5. Host tiling protocol
- TODO: how a host decomposes an arbitrary GEMM into tiles, ordering, K-accumulation across
  tiles, streaming format for weights/activations, result drain. (Expanded in INTEGRATION.md.)

## 6. Register / CSR map
- TODO: control, descriptor regs/queue, status, IRQ, perf counters, test-enable. Generated from
  `regs/tensortile.rdl` (PeakRDL). Mirrored in INTEGRATION.md.

## 7. Host interface (SPI → APB3)
- TODO: SPI slave framing, APB3 bridge, CSR access, status + IRQ on tile/layer completion.

## 8. Pin map (TT)
- TODO: `ui_in/uo_out/uio_*` assignments (SPI, IRQ, test mode). Drives `info.yaml`. **TBD until
  this section is frozen** (touching the pin map requires operator sign-off).

## 9. Feature ladder & area fallback
- P0 / P1 / P2 per master spec §4; area fallback ladder (drop P2 → bias → descq 4→2 → ARRAY_N
  4→3 → ACC_W 24→20 w/ overflow analysis → never compromise saturation/rounding; never drop
  perf counters or scan once implemented; ping-pong dropped only with operator approval).
