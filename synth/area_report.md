# Synthesis area/flops — first pass (generic Yosys, Phase 3)

> **Generic-gate proxy, not sky130.** Run `make synth` (Yosys 0.33, `synth/synth_area.ys`). No PDK
> liberty yet, so "cells" are Yosys generic gates ($_AND_/$_MUX_/...), which over-count vs sky130
> standard cells (ABC + a real liberty pack logic into complex AOI/OAI cells). **Flop counts and
> the relative per-block split are accurate; real µm² + sky130 cell count arrive in Phase 7 PnR.**

Config: ARRAY_N=4, DATA_W=8, ACC_W=24, BIAS_W=16, MAX_COLS=8.

| block | generic cells | flip-flops | notes |
|-------|---------------|-----------|-------|
| `tt_pe` (×16) | 833 ea (~13,328) | 24 ea (384) | INT8×INT8 multiply + 24b psum reg; **multipliers dominate** |
| `tt_mac_array` (excl. PEs) | 196 | 180 | weight mem 16×8=128 + row-skew SRs 48 + valid pipe |
| `tt_requant` | 1,013 | 0 | combinational: bias add, variable round-half-up shift, clamp |
| `tensortile_core` (excl. submods) | ~3,507 | 902 | **acc buffer 4×8×24 = 768 ff** + bias_rf 64 + FSM; MUX-heavy buffer addressing |
| **total (flattened)** | **~18,044** | **1,466** | 16 INT8 MACs are the area driver |

Observations / watch-items:
- The accumulator buffer (`ACC[ARRAY_N][MAX_COLS]`, 768 ff) and its index muxes are the largest
  single contributor after the multiplier array. `MAX_COLS` is the obvious area knob (DSE, Phase 7).
- 16 INT8 multipliers are the irreducible compute core (as expected for a GEMM tile).
- Utilization vs the ~12–16k sky130 cell budget cannot be judged from generic gates; deferred to
  the Phase 7 sky130 flow. Tracked here so the trend is visible from the first synth onward.
