# STATUS — TensorTile

_Update this every session. Single source of truth for "where are we."_

- **Current phase:** Phase 5 — P1 features (in progress). Flagship MNIST-through-RTL + compiler
  + perf counters + bias done & closure re-met; ping-pong + 4-deep descriptor queue remain.
- **Branch:** `claude/inspiring-allen-bw0cx`
- **Last updated:** 2026-06-07
- **Target shuttle:** Tiny Tapeout TTSKY26c (sky130A), submission deadline 2026-09-07
- **Operator directive:** proceed through phases without stopping at gates; commit each gate.

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

## Phase 1 results
- SPEC §2 arithmetic frozen (round-half-up) with 15 worked examples, all verified by tests.
- Golden model: `gemm_ref.py` (GEMM + requant + K-tiling) + `mlp_ref.py`; **26/26 model tests
  pass**. Bit-exact integer path; K-tiled == full GEMM proven.
- MNIST 8×8 (sklearn digits, offline): **float 97.33% / INT8 96.67%** (frozen weights committed).
- Descriptor format (§4), host tiling protocol (§5), pin map (§8) defined.

## Phase 2 results
- RTL (parametric, lint-clean -Wall): `tt_pe`, `tt_mac_array` (systolic, row-skew, psum-down),
  `tt_requant` (SPEC §2), `tt_fifo` (FWFT), `tensortile_core` (FSM + K-accum buffer + bias + requant).
- cocotb lockstep vs NumPy model — **4/4 benches pass** (array, requant, fifo, core); core covers
  single-tile, K-tiling, bias, ReLU, and 25 random shapes — all bit-exact. `make sim` runs them.

## Phase ladder
- [x] **Phase 0 — Scaffold** (smoke green local+CI, committed d5d6b7e)
- [x] **Phase 1 — Spec + golden model + MNIST** (26/26 tests; INT8 96.67%)
- [x] **Phase 2 — P0 RTL + lockstep** (PE→array→requant/fifo→core; 4/4 benches bit-exact)
- [x] **Phase 3 — DV closure** (1,000,160 MACs, 0 mismatches, 100% func cov 26/26)
- [x] **Phase 4 — Formal** (FIFO safety + core FSM/accumulator proven by k-induction)
- [~] **Phase 5 — P1 features** ← in progress
  - [x] end-to-end MNIST through RTL: **100/100 images bit-exact vs model, 96.00% silicon acc**
  - [x] compiler (`compiler/tiler.py`): MLP → 4×4 tiled descriptors/streams
  - [x] per-output bias (since Phase 2) · perf counters (busy/MACs/stall-by-cause), validated
  - [x] closure re-met: fast benches + 1M regression + formal all green with the changes
  - [ ] ping-pong weight double-buffer · [ ] 4-deep descriptor command queue (remaining P1 RTL)
- [ ] Phase 6 — DFT (scan + ATPG ≥95%) — **Fault tool unavailable in-env → CI/later**
- [~] Phase 7 — Hardening + DSE
  - [x] **sky130 area DSE** (real, yosys+PDK): core 93% util @N4/MC8; Pareto in pnr/dse_report.md
  - [ ] Fmax (OpenSTA) · placement util + **GDS** (OpenROAD/LibreLane) — **CI/later (not in-env)**
  - [ ] freeze PREDICTIONS.md at operator-selected tapeout point (area preliminary recorded)
- [x] **INTEGRATION.md** written (host tiling protocol centerpiece)
- [ ] Phase 8 — Release (datasheet, RP2040 fw, v1.0.0)

## Next actions (Phase 2 — RTL bottom-up, each level lockstep before composing)
1. `pe.v` → `row.v` → `array.v` → `accumulator`/`requant`/`fifo` → `tensortile_core` → CSR/SPI
   → real `tt_um_tensortile`. Fully parametric in ARRAY_N/DATA_W/ACC_W.
2. cocotb lockstep bench at each level vs `model/gemm_ref.py` (bit-exact). Then random GEMM
   tiles end-to-end through the core. Gate: bit-exact, lint clean.

## Open risks / watch-items
- Multipliers dominate area; ARRAY_N=4 INT8 = 16 MACs. Track area/flops from first synth.
- cocotb is 2.0.x (API differs from 1.x) — verify bench idioms in Phase 2.
- TT GDS layout (info.yaml/src) to be reconciled with spec §3 tree in Phase 7.
