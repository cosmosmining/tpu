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

## Full-chip area (tt_um_tensortile, measured — supersedes core-only for the tapeout point)

Real sky130 (`sky130_fd_sc_hd` tt) yosys synthesis of the **whole chip** (SPI host + CSR/bridge +
4-deep descriptor queue + I/O FIFOs + core), default ARRAY_N=4/DATA_W=8/ACC_W=24. The wrapper adds
~23.4k µm² over the core. Util vs TT die: 4×2=128,000 / 6×2=192,000 / 8×2=256,000 µm²; target ≤70%.

| MAX_COLS | full-chip cells | area µm² | 4×2 util | 6×2 util | 8×2 util |
|---------:|----------------:|--------:|---------:|---------:|---------:|
| 8 | ~16,900 | 142,669 | 111% ✗ | 74% ✗ | **56% ✓** |
| 4 | ~15,000 | 125,857 |  98% ✗ | **66% ✓** | 49% ✓ |
| 2 | ~14,100 | 117,898 |  92% ✗ | **61% ✓** | 46% ✓ |

**Read it straight:** the full chip does **not** fit a 4×2 TT die at ≤70% util in any config — the
SPI/CSR/FIFO/queue wrapper pushes even MC=2 to 92% of 4×2. Meeting ≤70% needs a larger die. The
gate-meeting tapeout points are: **MC4 @ 6×2 (66%)**, **MC2 @ 6×2 (61%)**, or **MC8 @ 8×2 (56%)**.
At a 6×2 die MC4 dominates MC2 (more batch, still ≤70%), so the choice is essentially MC4 @ 6×2
(smaller die, M≤4 per descriptor) vs MC8 @ 8×2 (largest die, full M≤8). MNIST (M=1) is unaffected
by MAX_COLS either way. Areas are pre-place std-cell sums; placement util (OpenROAD) + Fmax
(OpenSTA) remain CI/later.

## FROZEN tapeout point (2026-06-07)
**ARRAY_N=4, MAX_COLS=4, ACC_W=24, 6×2 tiles** (operator-selected). Full-chip ~124–126k µm² →
**~65% util** of the 6×2 die (192,000 µm²), ≤70% ✓. `make predict` re-derives + gates this. The
shipping RTL default is now MAX_COLS=4, so the hardened netlist == the verified config.
