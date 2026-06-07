# STATUS — TensorTile

_Update this every session. Single source of truth for "where are we."_

- **Current phase:** Phase 0 — Scaffold (awaiting operator gate approval)
- **Branch:** `claude/inspiring-allen-bw0cx`
- **Last updated:** 2026-06-07
- **Target shuttle:** Tiny Tapeout TTSKY26c (sky130A), submission deadline 2026-09-07

## Last results (Phase 0)
- Repo scaffolded to spec §3 (full tree, brain files, docs stubs, model/RTL/DV/PD dirs).
- Tools provisioned: **verilator 5.020, iverilog, numpy 2.4.6, cocotb 2.0.1, pytest 9.0.3**
  (pip + apt). Heavy/CI tools (yosys, sby, verible, openroad, fault, peakrdl) documented in
  DECISIONS.md, provisioned in later phases / CI.
- `make smoke`: known-answer INT8 matmul + compile of `tt_um_tensortile` interface stub
  (iverilog + verilator). **Result: see METRICS / gate report.**
- CI workflows added: lint / test / formal / gds (manual) / nightly.
- Hooks: PostToolUse (lint+compile after `rtl/` edits) + SessionStart (re-provision tools).
- Slash commands: /regress /lockstep /timing /sweep /status.

## Phase ladder (stop at every gate)
- [ ] **Phase 0 — Scaffold** ← awaiting "continue"
- [ ] Phase 1 — Spec + golden model + MNIST demo workload
- [ ] Phase 2 — P0 RTL + lockstep (PE→row→array→control)
- [ ] Phase 3 — DV closure on P0 (≥1M MACs, ≥95% func cov)
- [ ] Phase 4 — Formal (FIFO/FSM/descq/accumulator)
- [ ] Phase 5 — P1 features (ping-pong, desc queue, bias, counters, MNIST demo)
- [ ] Phase 6 — DFT (scan + ATPG ≥95%)
- [ ] Phase 7 — Hardening + DSE + frozen PREDICTIONS.md + green GDS
- [ ] Phase 8 — Release (datasheet, INTEGRATION, RP2040 fw, v1.0.0)

## Next actions (proposed — pending operator approval)
1. Operator reviews Phase 0 gate report; says "continue."
2. Phase 1: draft `docs/SPEC.md` arithmetic definition (accumulation width/signedness,
   saturation bounds per stage, requant rounding rule + worked edge cases), then the NumPy
   golden GEMM/MLP references with unit tests, MNIST train/quant + frozen weights, descriptor
   format, host tiling protocol, and `docs/VPLAN.md`. **SPEC freeze is operator-gated.**

## Open risks / watch-items
- Multipliers dominate area; ARRAY_N=4 INT8 = 16 MACs. Track area/flops from first synth.
- cocotb is 2.0.x (API differs from 1.x) — verify bench idioms in Phase 2.
- TT GDS layout (info.yaml/src) to be reconciled with spec §3 tree in Phase 7.
