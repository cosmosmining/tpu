# rtl/core — TensorTile core (Phase 2+)

Parametric `tensortile_core` and submodules, built strictly bottom-up with lockstep verification
at every level (engineering standard #4):

- `pe.v` — processing element: weight register, INT8×INT8 MAC, partial-sum pass-down.
- `row.v` — a row of PEs with activation skew.
- `array.v` — ARRAY_N×ARRAY_N systolic array.
- `accumulator.v` — ACC_W signed column accumulators with K-tiling accumulate-enable.
- `requant.v` — bias (P1) → arithmetic-shift requant w/ spec rounding → INT8 saturate → ReLU.
- `fifo.v` — synchronous FIFO (≤16 deep) for activation-in / result-out.
- `control.v` — descriptor decode + FSM; descriptor queue (P1); ping-pong (P1).
- `csr.v` — APB3 CSR block generated from `regs/tensortile.rdl` (PeakRDL).

All modules are fully parametric in `ARRAY_N`/`DATA_W`/`ACC_W` (never hardcoded). No SRAM macros
(all flops), no latches, synchronous active-low reset, single clock domain.

> Phase-0: placeholder. The interface-only top stub lives in `rtl/tt_top/tt_um_tensortile.v`.
