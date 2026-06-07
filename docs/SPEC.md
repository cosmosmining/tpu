# SPEC — TensorTile

> **FROZEN: YES (working contract).** Arithmetic frozen on the operator's decision (requant =
> **round-half-up**, 2026-06-07) and the directive to proceed through the phase ladder. The
> worked examples in §2 are generated from and **verified by** `model/test_gemm_ref.py` (silicon
> = RTL = `model/gemm_ref.py`, to the bit). Any change here requires a DECISIONS.md entry; the
> golden model must never be edited merely to make RTL pass.

## 0. Conventions & parameters
- Two's-complement signed integers throughout. Bit `[MSB:LSB]`, little-endian fields in CSRs.
- Top-level parameters (never hardcode): `ARRAY_N=4`, `DATA_W=8` (INT8), `ACC_W=24` (signed).
- Derived: `INT8 ∈ [-128,127]`, `ACC ∈ [-2^23, 2^23-1]`, bias `∈ [-2^15, 2^15-1]` (16-bit, P1).

## 1. Function overview
Weight-stationary INT8 systolic GEMM tile. An `ARRAY_N×ARRAY_N` PE grid holds a weight tile;
activations stream in column-by-column with row skew; products accumulate down columns into
`ACC_W` accumulators. Column accumulators support **multi-tile K-accumulation** (carry across
K-tiles) so a host can tile arbitrarily large GEMMs. The output path is
`{bias (P1) → requant shift → optional saturating ReLU} → output FIFO`.

## 2. Arithmetic definition (THE CONTRACT)
For an output element with output-row `n` and column `m`:

```
(1) acc[n,m] = Σ_k  W[n,k] * A[k,m]          # INT8×INT8 products, exact, signed; K may span tiles
(2) t        = acc[n,m] + bias[n]            # bias signed 16-bit (P1); bias = 0 if disabled
(3) r        = round_half_up(t, shift)       # arithmetic right shift; ties round toward +∞
(4) y[n,m]   = clamp(r, lo, 127),  lo = 0 if relu else -128     # saturate to INT8
```

### 2.1 Products and accumulation
- `W[n,k], A[k,m] ∈ [-128,127]`. Product range `[-16256, +16384]` (note `(-128)*(-128)=+16384`,
  `127*(-128)=-16256`) — **fits in 16 bits**, computed exactly, no rounding, no abs().
- `acc` is `ACC_W=24`-bit signed two's-complement, **non-saturating**. Valid descriptors must not
  overflow it (see §2.3). K-accumulation adds successive K-tile partial sums into `acc` (carry).
- Bias is added **once**, on the final K-tile, immediately before requant (step 2).

### 2.2 Requantization rounding rule — round half up (operator-frozen)
```
round_half_up(t, s) = t                                if s == 0   (exact passthrough)
                    = (t + (1 << (s-1))) >> s          if s >= 1   (>> = arithmetic shift)
```
This is `floor((t + 2^(s-1)) / 2^s)`: halfway cases round toward **+∞** (for both signs). Then
clamp to INT8; with ReLU the lower clamp bound is 0. `shift` is per-descriptor, `0..31`.

### 2.3 Accumulator overflow bound
Worst-case |product| = 16384, so `acc` stays in 24-bit range for up to
`floor((2^23-1)/16384) = 511` worst-case accumulated products. With `ARRAY_N=4`, a single tile
contributes ≤4 products (≤65536); the host must keep total `K ≤ 511` *adversarial* terms (real NN
magnitudes are far smaller — the MNIST demo's max |acc| is well within range). The K-tiled model
(`quant_gemm_ktiled`) raises `OverflowError` if this is violated; the area-fallback to `ACC_W=20`
requires re-deriving this bound (SPEC §9).

### 2.4 Worked examples (verified by `model/test_gemm_ref.py`)
| # | inputs | computation | result |
|---|--------|-------------|--------|
| E1 | t=5, s=0 | passthrough | **5** |
| E2 | t=6, s=2 | 6/4=1.5 → half-up | **2** |
| E3 | t=5, s=2 | 5/4=1.25 | **1** |
| E4 | t=7, s=2 | 7/4=1.75 | **2** |
| E5 | t=−6, s=2 | (−6+2)>>2 = (−4)>>2; −1.5 → toward +∞ | **−1** |
| E6 | t=−7, s=2 | −7/4=−1.75 | **−2** |
| E7 | t=−2, s=2 | −0.5 → toward +∞ | **0** |
| E8 | acc=300, s=0 | 300 > 127 → saturate | **127** |
| E9 | acc=−300, s=0 | < −128 → saturate | **−128** |
| E10 | acc=−300, s=0, relu | lower bound 0 | **0** |
| E11 | acc=−5, s=0, relu | ReLU | **0** |
| E12 | acc=100, bias=27, s=0 | 127 | **127** |
| E13 | acc=100, bias=28, s=0 | 128 → saturate | **127** |
| E14 | W=A=−128 | product | **+16384** |
| E15 | 4×(−128·−128)=65536, s=9 | (65536+256)>>9 = 128 → saturate | **127** |

## 3. Microarchitecture / dataflow
- **PE**: holds one weight reg; each cycle computes `w*a`, adds the partial sum from above, passes
  the activation right and the partial sum down. Latency 1 cycle/stage.
- **Row / Array**: `ARRAY_N` PEs per row, `ARRAY_N` rows. Activations enter with **row skew**
  (row `i` delayed `i` cycles) so a column's contributions align in the column accumulator.
- **Column accumulator**: `ACC_W` register per column; `accumulate_en` selects `0 + partial`
  (first K-tile) vs `acc + partial` (subsequent K-tiles).
- **Weight load**: shift-chain preload; **ping-pong** double buffer (P1) loads the next tile's
  weights while the current tile computes.
- **Requant unit**: `bias add → round-half-up shift → clamp(lo,127)`; one element/cycle drain.
- **FIFOs**: activation-in and result-out, synchronous, depth ≤16, flops only.

## 4. Descriptor format
A descriptor programs one accumulate-group producing an `ARRAY_N×num_cols` output tile,
accumulated over `num_k_tiles` K-tiles. CSR-programmed (single descriptor P0; 4-deep queue P1).
64 bits:

| bits | field | meaning |
|------|-------|---------|
| [7:0]   | `num_cols`     | activation columns M to stream (1..255) |
| [15:8]  | `num_k_tiles`  | K-tiles to accumulate; K = num_k_tiles·ARRAY_N (1..255) |
| [20:16] | `requant_shift`| arithmetic-shift amount s (0..31) |
| [21]    | `relu_en`      | saturating ReLU on output |
| [22]    | `bias_en`      | add per-row bias before requant (P1) |
| [23]    | `chain`        | continue column accumulators from previous descriptor (P1) |
| [31:24] | reserved       | 0 |
| [63:32] | reserved       | bias/weight base pointers (P1) |

## 5. Host tiling protocol
To compute `Y(Nout×M) = requant(W(Nout×K) · A(K×M) + bias)`:
1. **Row-tile** Nout into `⌈Nout/ARRAY_N⌉` tiles; **K-tile** K into `⌈K/ARRAY_N⌉` tiles; stream M
   columns (split into `num_cols≤255` chunks if larger).
2. For each output row-tile:
   a. Preload weights for K-tile 0; (P1) ping-pong-load K-tile 1 while computing.
   b. Stream activation columns; products accumulate into the column accumulators with
      `accumulate_en` = (k_tile==0 ? clear : accumulate).
   c. Repeat for all `num_k_tiles`; add `bias` on the final K-tile.
   d. `requant_shift` + `relu` → results drain to the output FIFO in column order.
3. Status/IRQ asserts on tile/layer completion; the host reads results and advances.

The full streaming byte format (SPI framing) and CSR sequence are in `docs/INTEGRATION.md`.

## 6. Register / CSR map
Generated from `regs/tensortile.rdl` (PeakRDL). Control (start/relu/bias/test-enable),
descriptor regs / 4-deep queue (P1), status (busy/done/overflow/queue-occupancy), IRQ
enable/status, performance counters (busy cycles, MACs issued, utilization, stall-by-cause).
Mirrored in INTEGRATION.md.

## 7. Host interface (SPI → APB3)
SPI slave (mode 0) → APB3 bridge → CSR block. 8-bit SPI frames: `{R/W, addr}` then data. Status
+ maskable IRQ on tile/layer completion. Details in INTEGRATION.md.

## 8. Pin map (TT)
| pin | dir | normal mode | test mode (`test_en`) |
|-----|-----|-------------|-----------------------|
| `ui_in[0]` | in | SPI SCLK | scan clock |
| `ui_in[1]` | in | SPI CSn | scan_en |
| `ui_in[2]` | in | SPI MOSI | scan_in[0] |
| `ui_in[7:3]` | in | reserved (0) | scan_in[5:1] |
| `uo_out[0]` | out | SPI MISO | scan_out[0] |
| `uo_out[1]` | out | IRQ | scan_out[1] |
| `uo_out[2]` | out | busy | scan_out[2] |
| `uo_out[3]` | out | done | scan_out[3] |
| `uo_out[7:4]` | out | reserved (0) | scan_out[7:4] |
| `uio[7:0]` | bidir | inputs, `uio_oe=0` (P0 unused) | scan chain extension (Phase 6) |

Scan is muxed onto the pins under the `test_en` CSR bit (Phase 6). This drives `info.yaml`.

## 9. Feature ladder & area fallback
P0 / P1 / P2 per the master spec. Area fallback (apply top-down if util >70%): drop P2 → drop
bias → descriptor queue 4→2 → `ARRAY_N` 4→3 → `ACC_W` 24→20 **with a rewritten §2.3 overflow
analysis** → never compromise saturation/rounding correctness; never drop perf counters or scan
once implemented; ping-pong dropped only with operator approval (last resort before `ARRAY_N`↓).
