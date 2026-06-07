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

| metric | predicted | basis |
|--------|-----------|-------|
| _(frozen in Phase 7)_ | | |

---

### Addenda (post-freeze corrections only — dated)
_none yet_
