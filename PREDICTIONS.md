# PREDICTIONS — TensorTile (pre-registered, frozen at tapeout)

> **Status: FROZEN 2026-06-07** at the operator-selected tapeout point: **ARRAY_N=4, MAX_COLS=4,
> ACC_W=24, 6×2 TT tiles**. Area/util/throughput are pre-registered from real sky130 synthesis;
> routed Fmax + placement util are pre-registered as **targets**, to be graded against OpenSTA/
> OpenROAD in CI. After this freeze the table is **never edited** — corrections go to the dated
> addendum. Purpose: honest pre-registration so the project grades itself, not rationalizes after.

## Frozen tapeout point — ARRAY_N=4, MAX_COLS=4, ACC_W=24, 6×2 tiles

| metric | pre-registered value | grade source | basis |
|--------|----------------------|--------------|-------|
| Full-chip area | **~124,300–125,900 µm²** (~15.0k sky130 cells; ±1% abc-run variance) | OpenROAD GDS | yosys + sky130_fd_sc_hd tt (full top; `make predict`) |
| — core (PE×16 + ACC@MC4 + requant + FSM) | ~101,200 µm² (~80%) | — | DSE row N4/MC4 (pnr/dse_report.md) |
| — wrapper (SPI host + 2 FIFOs + descriptor queue + CSR) | ~23,100 µm² (~20%) | — | full-chip − core |
| Synthesis utilization (full chip) | **64.8–65.6%** of 6×2 die (192,000 µm²) | OpenROAD placement | ≤70% target met (`make predict` re-derives + gates) |
| Dominant area | 16 INT8 multipliers (irreducible) + ACC buffer (256 ff @ MC4) | — | DSE read-out |
| Peak compute | **16 MAC/cycle** (ARRAY_N²) | — | weight-stationary array, 1 col/cycle |
| **Routed Fmax (tt corner)** | **≥ 50 MHz** (target; WNS ≥ 0) | **OpenSTA (CI)** | _pre-registered target — grade in CI_ |
| Peak throughput @ 50 MHz | **0.8 GMAC/s** | OpenSTA-closed freq | 16 MAC/cycle × 50 MHz |
| Demo-workload accuracy (silicon) | **96.00%** (100-img), 96.67% (full) | already measured | RTL bit-exact vs NumPy model |
| Demo-workload MAC utilization | pre-registered _pending perf-counter dump on routed clk_ | perf counters | `perf_mac / (perf_busy·16)` |

**Pre-registration call:** routed Fmax meets the 50 MHz target with WNS ≥ 0 at the tt corner, and
placement util stays ≤70% on the 6×2 die. These two are graded against OpenSTA/OpenROAD in CI; the
GDS itself is produced by the TT gds action. The verified RTL config (lint/1M-MAC/formal/MNIST) is
exactly this tapeout point (MAX_COLS=4) — see METRICS row dated 2026-06-07.

---

### Addenda (post-freeze corrections only — dated)
_none yet_
