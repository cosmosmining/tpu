# STATUS — TensorTile

_Update this every session. Single source of truth for "where are we."_

- **Current phase:** Phase 7 — tapeout point FROZEN (N4/MC4/ACC24, 6×2). **Official TTSKY26c GDS
  signoff wired + iterating** (tt-gds-action@ttsky26c). Cleared 3 gates: pinout schema, `src/config.json`,
  and a real RTL fix (`tensortile_core` shared loop var → 32 OpenLane synth-check errors → fixed,
  re-verified bit-exact). **Run #4 (38e54c9) now in OpenLane P&R.** ⚠️ Watch: OpenLane synth area
  = **165k µm²** (vs yosys-predicted 124k) ⇒ 6×2 util likely ~85% (> the 70% gate) — run #4 will
  show if it places/routes; 8×2 is the fallback (DSE: ~49%). Remaining = grade result, precheck/
  gl_test/viewer + LICENSE + v1.0.0 tag.
- **Branch:** `claude/inspiring-allen-bw0cx` — NB: container re-clones from origin between sessions;
  `git pull` before working (a stale local base caused a rebase recovery this session).
- **Last updated:** 2026-06-08
- **Target shuttle:** Tiny Tapeout TTSKY26c (sky130A), submission deadline 2026-09-07
- **Operator directive:** proceed through phases without stopping at gates; commit each gate.

## Headline results (cumulative)
- **Bit-exact** spec/model/RTL: SPEC §2 frozen (round-half-up); 26/26 model tests; golden GEMM/MLP.
- **DV:** cocotb lockstep PE→array→requant→fifo→core; **1,000,160 MACs, 0 mismatches, 100% func
  cov (26/26)** (`make regress` → dv/coverage_phase3.md).
- **Formal:** FIFO safety + core FSM/accumulator proven by **k-induction** (unbounded) (`make formal`).
- **Flagship:** 8×8 MNIST through the RTL core — **100/100 images bit-exact vs model, 96.00% silicon
  accuracy** (`make demo`); compiler in `compiler/tiler.py`; perf counters validated.
- **PD (real sky130, area):** **full chip @ frozen point (N4/MC4) = 124–126k µm² / ~15k cells /
  65% util of 6×2** (≤70% ✓, `make predict` gates it). 4×2 die infeasible (full chip 98–111%); DSE
  +full-chip table in pnr/dse_report.md. Fmax/placement util/GDS = CI/later (graded vs PREDICTIONS).
- Tools (in-env): verilator 5.020, iverilog, yosys 0.33, numpy 2.4.6, cocotb 2.0.1, sklearn,
  sky130_fd_sc_hd PDK (volare). Blocked-in-env (CI/later): OpenSTA, OpenROAD/LibreLane, Fault.
- CI: lint / test / formal green; gds (manual/tag); nightly (full regress). Hooks + slash commands live.

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
  - [x] **4-deep descriptor command queue** (`tensortile_engine`, reuses proven `tt_fifo`):
    enqueue/occupancy/full + back-to-back execution, all results bit-exact (`tb_engine`)
  - [x] ping-pong: **evaluated, intentionally not shipped** — no benefit with single-cycle weight
    load + area-negative (DECISIONS/ERRATA E6); dual-bank path verified, overlap reverted unverified
- [ ] Phase 6 — DFT (scan + ATPG ≥95%) — **Fault tool unavailable in-env → CI/later**
- [~] Phase 7 — Hardening + DSE
  - [x] **sky130 area DSE** (real, yosys+PDK): core 93% util @N4/MC8; Pareto in pnr/dse_report.md
  - [ ] Fmax (OpenSTA) · placement util + **GDS** (OpenROAD/LibreLane) — **CI/later (not in-env)**
  - [x] **PREDICTIONS.md FROZEN** at the operator-selected point (N4/MC4/ACC24, 6×2); area gate
    re-derived + enforced by `make predict` (65% util); Fmax/placement pre-registered as CI-graded targets
- [x] **INTEGRATION.md** written (host tiling protocol centerpiece)
- [~] Phase 8 — Release
  - [x] **DATASHEET.md** (arch/arithmetic/perf/area/verification consolidated)
  - [x] **RP2040 demo firmware** (`fw/`: driver + MNIST demo, compile-clean; HW-untested)
  - [x] compiler weights export (`compiler/export.py` → `fw/mnist_weights.h`)
  - [x] **SPI/CSR top integration**: `tt_um_tensortile` = SPI-slave → CSR/bridge (`tt_spi_host`)
    → descriptor queue + core; **end-to-end GEMM over SPI bit-exact** (`tb_top`); smoke compiles
    the full hierarchy; 7/7 fast benches green
  - [ ] tag v1.0.0 (after a frozen tapeout point + GDS in CI)

## Next actions (Phase 2 — RTL bottom-up, each level lockstep before composing)
1. `pe.v` → `row.v` → `array.v` → `accumulator`/`requant`/`fifo` → `tensortile_core` → CSR/SPI
   → real `tt_um_tensortile`. Fully parametric in ARRAY_N/DATA_W/ACC_W.
2. cocotb lockstep bench at each level vs `model/gemm_ref.py` (bit-exact). Then random GEMM
   tiles end-to-end through the core. Gate: bit-exact, lint clean.

## Open risks / watch-items
- Multipliers dominate area; ARRAY_N=4 INT8 = 16 MACs. Track area/flops from first synth.
- cocotb is 2.0.x (API differs from 1.x) — verify bench idioms in Phase 2.
- TT GDS layout (info.yaml/src) to be reconciled with spec §3 tree in Phase 7.
