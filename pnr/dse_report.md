# Phase 7 — Design-Space Exploration (sky130 area)

> Real sky130 (`sky130_fd_sc_hd`, tt corner) synthesis via yosys (`make sweep`, volare PDK).
> **Area axis only** — Fmax needs OpenSTA and full utilization needs OpenROAD PnR, both
> CI/later in this environment (see DECISIONS.md). Area = Σ std-cell areas (pre-place); util vs
> the 4×2 TT die (~128,000 µm²); target ≤70%. **Core only** (add I/O FIFOs + SPI/CSR for full-chip).

| config (ARRAY_N, MAX_COLS, ACC_W) | sky130 cells | area µm² | util % |
|-----------------------------------|-------------:|--------:|-------:|
| 4, 8, 24  (full P0+P1)            | ~16,100 | 119,231 | **93.1** |
| 4, 4, 24                          | ~14,600 | 101,202 | 79.1 |
| 4, 2, 24                          | ~13,900 |  93,352 | 72.9 |
| 4, 8, 20  (ACC fallback)          | ~14,800 | 108,786 | 85.0 |
| **3, 4, 24**                      | **~8,900** | **62,935** | **49.2** |

## Read it straight
- At **ARRAY_N=4, MAX_COLS=8** the compute core alone is **93% util** — over the ≤70% target;
  adding FIFOs + SPI/CSR would not fit a 4×2 die at a healthy density. Cell **count** (~14–16k) is
  within the spec's 12–16k budget, but **cell area** is the binding constraint here.
- Dominant area: the **16 INT8 multipliers** (irreducible) and the **accumulator buffer**
  (`ACC[ARRAY_N][MAX_COLS]`, 768 ff at MC=8) with its index muxes.
- **`MAX_COLS` is the clean knob** (area-fallback ladder): MC 8→2 drops util 93%→73% and **does not
  affect the MNIST demo** (inference is M=1; the host tiles M). MC=4 is a middle point.
- **ARRAY_N=3** is roomy (49%) but K must be a multiple of ARRAY_N; the MLP's 64- and 32-wide
  layers tile cleanly only at ARRAY_N=4 (would need K-padding at 3). So ARRAY_N=4 is preferred for
  the flagship; shrink via MAX_COLS instead.

## Recommendation (operator picks the tapeout point — SPEC)
For 4×2 at ≤70% util including the wrapper, **ARRAY_N=4, MAX_COLS=2** (core 73%) plus a possible
ACC_W=20 (with a re-derived §2.3 overflow bound) is the leading candidate; alternatively request a
larger tile (e.g. 6×2). Peak throughput = ARRAY_N²·f = 16 MAC/cycle × 50 MHz = **0.8 GMAC/s** at
the target clock (closed Fmax pending OpenSTA). The operator selects the point; do not auto-decide.
