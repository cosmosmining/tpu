# TensorTile — Datasheet (preliminary)

**Weight-stationary INT8 systolic GEMM accelerator IP** for Tiny Tapeout (TTSKY26c / sky130).
On-chip per-tensor requantization; multi-tile K-accumulation for arbitrarily large GEMMs.
Flagship: a 2-layer quantized MLP classifying 8×8 MNIST digits, **bit-exact silicon = RTL = NumPy**.

## Features
- ARRAY_N×ARRAY_N (default **4×4**) weight-stationary systolic MAC array, INT8×INT8.
- 24-bit signed accumulators; multi-tile K-accumulation (host tiles any K).
- Per-tensor requant: bias (16b) → **round-half-up** arithmetic shift → saturating INT8 / ReLU.
- 4-deep descriptor command queue (P1); performance counters (MACs, busy, stall-by-cause).
- SPI-slave host interface (→APB3→CSR); single clock; flops only (no SRAM macros).
- Fully parametric (ARRAY_N / DATA_W / ACC_W / BIAS_W / MAX_COLS).

## Arithmetic (the contract — bit-exact, frozen)
`y[n,m] = clamp( round_half_up( (Σ_k W[n,k]·A[k,m]) + bias[n], shift ), relu?0:-128, 127 )`
where `round_half_up(t,s) = (t + (1<<(s-1))) >>> s` (s>0), exact passthrough at s=0. Defined by
`model/gemm_ref.py`; see SPEC §2 for worked edge cases (saturation, ties, most-negative operands).

## Key specifications
| parameter | value | notes |
|-----------|-------|-------|
| Array | 4×4 INT8 MACs | 16 MAC/cycle peak |
| Operands | INT8 (−128..127) | weights + activations |
| Accumulator | 24-bit signed | K ≤ 511 adversarial terms (SPEC §2.3) |
| Target clock | 50 MHz | post-route Fmax: TBD (OpenSTA, CI) |
| Peak throughput | **0.8 GMAC/s** | 16 MAC/cycle × 50 MHz |
| Process | sky130 (`fd_sc_hd`) | TTSKY26c shuttle |
| Core area (N4, MAX_COLS=8) | **119,231 µm² / ~14–16k cells** | yosys + sky130 tt (make sweep) |
| Core area (N4, MAX_COLS=2) | 93,352 µm² | area-fallback point |
| Die budget | 4×2 tiles (~128,000 µm²) | utilization target ≤70% |

## Demo workload — 8×8 MNIST MLP
| metric | value |
|--------|-------|
| Network | 64→32 (ReLU) →10, INT8, power-of-two requant |
| Float accuracy | 97.33% |
| **INT8 accuracy (silicon target)** | **96.67%** (full test set) |
| RTL demo | **100/100 images bit-exact vs model**, 96.00% (100-img subset) |

## Verification status
- Lockstep cocotb PE→array→requant→fifo→core→engine, all **bit-exact** vs the NumPy model.
- Constrained-random regression: **1,000,160 MACs, 0 mismatches, 100% functional coverage (26/26)**.
- Formal (yosys k-induction, unbounded): FIFO safety; core FSM legal-state; accumulator index +
  write-conflict freedom.
- CI: lint / test / formal green; GDS via official TT Action (manual/tag).

## Interface (summary — see docs/INTEGRATION.md)
SPI mode-0 slave on `ui_in[2:0]` (SCLK/CSn/MOSI), `uo_out[0]`=MISO, `[1]`=IRQ, `[2]`=busy,
`[3]`=done. Scan muxed under `test_en` (Phase 6). Host tiling protocol + CSR map in INTEGRATION.md.

## Status & roadmap
Done: arithmetic+model+MNIST (P0/P1 compute), RTL+DV+formal, descriptor queue, perf counters,
sky130 area DSE. Pending (tool-gated → CI): Fmax (OpenSTA), GDS/utilization (OpenROAD), scan/ATPG
(Fault). Deferred by area tradeoff: ping-pong weight double-buffer (adds a bank; see DECISIONS.md).
Preliminary numbers freeze at the operator-selected tapeout point (PREDICTIONS.md).
