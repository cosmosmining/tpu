# PREDICTIONS — TensorTile (pre-registered, frozen at tapeout)

> **Status: NOT YET FROZEN.** Populated in Phase 7 *before* the official GDS run, then frozen.
> After freezing, this file is **never edited** — corrections go in a dated addendum at the
> bottom. Purpose: honest, pre-registered silicon predictions to compare against measured
> results, so the project grades itself instead of rationalizing after the fact.

To be recorded before tapeout (Phase 7), at the operator-selected design point:
- **OpenSTA Fmax** at the tt corner (and the closed target frequency).
- **Area per block** (PE, array, accumulators, requant, FIFOs, CSR, control) in cells + um².
- **Peak MAC utilization** (theoretical, back-to-back tiles).
- **Demo-workload MAC utilization** (measured on the streamed MNIST MLP).
- **Headline throughput** = MACs/cycle × closed frequency.

**Preliminary (NOT frozen — Fmax/PnR pending OpenSTA+OpenROAD in CI):**

| metric | preliminary value | basis |
|--------|-------------------|-------|
| Core area @ ARRAY_N=4, MAX_COLS=8 | 119,231 µm² (~14–16k sky130 cells) | yosys + sky130_fd_sc_hd tt (make sweep) |
| Core area @ ARRAY_N=4, MAX_COLS=2 | 93,352 µm² (~13.9k cells) | DSE point (pnr/dse_report.md) |
| Synthesis utilization (core, MC=8) | ~93% of 4×2 die | over ≤70% target → fallback needed |
| Peak compute | ARRAY_N² = 16 MAC/cycle | weight-stationary array |
| Peak throughput @ 50 MHz target | 0.8 GMAC/s | 16 MAC/cycle × 50 MHz |
| Demo-workload accuracy (silicon) | 96.00% (100-img MNIST), 96.67% (full) | RTL bit-exact vs model |
| **Fmax (OpenSTA), demo MAC util, closed throughput** | _pending_ | needs OpenSTA/OpenROAD (CI) |

These freeze (with Fmax) at the operator-selected tapeout point in Phase 7.

---

### Addenda (post-freeze corrections only — dated)
_none yet_
