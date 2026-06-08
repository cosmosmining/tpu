# METRICS — TensorTile (append-only)

Each row is one measurement point. **Append only — never edit or delete past rows.**
Rows are added by `scripts/metrics.py` (parses tool logs → `summary.json` → a row here) from
Phase 2 (first synth) onward; earlier rows are recorded by hand.

Columns:
- **date** — YYYY-MM-DD
- **commit** — short SHA the numbers describe
- **phase** — pipeline phase
- **func_cov** — functional coverage % (DV)
- **macs** — MAC operations exercised in regression
- **cells / area** — std-cell count / um² (per-block detail lives in synth/ reports)
- **WNS** — worst negative slack (ns) at stated corner/freq
- **util** — back-to-back-tile MAC utilization % (or place utilization for PD rows)
- **atpg** — stuck-at coverage %
- **notes**

| date | commit | phase | func_cov | macs | cells / area | WNS | util | atpg | notes |
|------|--------|-------|----------|------|--------------|-----|------|------|-------|
| 2026-06-07 | scaffold | 0 | n/a | n/a | n/a | n/a | n/a | n/a | Phase 0 scaffold; `make smoke` green (known-answer INT8 matmul + `tt_um_tensortile` stub compiled w/ iverilog+verilator). No synth/DV/PD yet. |
| 2026-06-07 | d5d6b7e | 1 | model 26/26 | n/a | n/a | n/a | n/a | n/a | Phase 1: SPEC arithmetic frozen (round-half-up); golden GEMM/MLP + 26 unit tests pass; MNIST 8×8 float 97.33% / **INT8 96.67%** (frozen weights). No RTL/synth yet. |
| 2026-06-07 | 454bd02 | 2 | lockstep 4/4 | directed+rand | n/a | n/a | n/a | n/a | Phase 2: P0 RTL (pe/array/requant/fifo/core), all -Wall clean; cocotb lockstep bit-exact vs model (single/K-tile/bias/relu/25 random). ≥1M-MAC campaign is Phase 3. No synth yet. |
| 2026-06-07 | bf86d22 | 3 | **100% (26/26)** | **1,000,160** | n/a | n/a | n/a | n/a | Phase 3: constrained-random + adversarial regression, **0 mismatches** over 3127 descriptors; functional coverage 26/26 bins (dv/coverage_phase3.md). Synth/PD next. |
| 2026-06-07 | ffb0662 | 3 | — | — | ~18k gen-gates / **1466 ff** | n/a | n/a | n/a | First Yosys generic synth (no PDK liberty): 16 INT8 MACs + 768-ff acc buffer dominate; per-block in synth/area_report.md. sky130 µm²/cells + WNS come in Phase 7. |
| 2026-06-07 | b49621a | 4 | formal ✓ | — | — | n/a | n/a | n/a | Phase 4: yosys-sat k-induction proofs PASS — FIFO safety (overflow/underflow/flags) + core FSM legal-state + accumulator index/conflict freedom. Unbounded (temporal induction). dv/formal/. |
| 2026-06-07 | 88cf001 | 5 | demo 100/100 | (1M held) | +perf ctrs | n/a | **96.00%** | n/a | Phase 5: end-to-end 8×8 MNIST through RTL core — **100/100 images bit-exact vs model**, silicon accuracy 96.00% (100-img subset). Compiler (4×4 tiler) + perf counters (MACs/busy/stall-by-cause) validated. util column = demo classification accuracy. |
| 2026-06-07 | 7064f1e | 7 | — | — | **sky130: 14–16k cells / 119,231 µm²** | Fmax: CI | **93.1% (MC=8)** | n/a | Phase 7 area DSE (real sky130_fd_sc_hd, yosys): core@N4,MC8 = 93% util (>70% — fallback needed); MC8→2 ⇒ 73%; N=3 ⇒ 49%. Pareto in pnr/dse_report.md. Fmax(OpenSTA)/GDS(OpenROAD) = CI/later. |
| 2026-06-07 | c1edbf3 | 7 | — | — | **full-chip sky130: ~16.9k cells / 142,669 µm² (MC8); 125,857 (MC4); 117,898 (MC2)** | Fmax: CI | **MC8 8×2=56%, MC4 6×2=66%, MC2 6×2=61%** | n/a | Full-chip area DSE (tt_um_tensortile, wrapper incl.). 4×2 die infeasible @≤70%; gate-meeting points need 6×2 (MC≤4) or 8×2 (MC8). |
| 2026-06-07 | (this) | 7 | **100% (26/26)** | **1,000,288** | **full-chip @ frozen N4/MC4: ~124–126k µm² / ~15k cells** | Fmax: CI (≥50MHz target) | **64.8% of 6×2** ✓≤70 | n/a | **Tapeout point FROZEN** (ARRAY_N=4, MAX_COLS=4, ACC_W=24, 6×2). Whole shipping config re-verified at MC4: lint/7-benches/formal/MNIST 100/100/1M-MAC 0-mismatch. PREDICTIONS.md frozen; `make predict` gates util. Fmax/GDS/ATPG = CI. |
