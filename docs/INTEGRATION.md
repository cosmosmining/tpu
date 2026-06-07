# INTEGRATION — TensorTile host & bring-up guide

How a host drives TensorTile: pin map, CSR map, the **host tiling protocol** (the centerpiece),
the streaming format, and bring-up. Reflects the implemented `tensortile_core` (Phases 2–5).

## 1. Pin map (TT, sky130A) — SPEC §8
| pin | dir | normal mode | test mode (`test_en`) |
|-----|-----|-------------|-----------------------|
| `ui_in[0]` | in | SPI SCLK | scan clock |
| `ui_in[1]` | in | SPI CSn | scan_en |
| `ui_in[2]` | in | SPI MOSI | scan_in |
| `uo_out[0]` | out | SPI MISO | scan_out |
| `uo_out[1]` | out | IRQ (tile/layer done) | scan_out |
| `uo_out[2]` | out | busy | — |
| `uo_out[3]` | out | done | — |
| `uio[7:0]` | bidir | reserved (`uio_oe=0`) | scan-chain extension |

Single clock (TT harness), target 50 MHz; synchronous active-low `rst_n`.

## 2. Core interface (what the SPI→APB→CSR wrapper drives)
`tensortile_core` (direct streaming interface, all parametric in ARRAY_N/DATA_W/ACC_W/BIAS_W/MAX_COLS):
- **Descriptor** (latched on `start`): `num_cols` (1..MAX_COLS), `num_k_tiles` (≥1),
  `requant_shift` (0..31), `relu_en`, `bias_en`.
- **Weights**: per K-tile, the core raises `w_req`; host pulses `w_load` with the N×N tile
  flattened as `w_flat[(k*N+c)*DATA_W +: DATA_W] = W[c][k]` (i.e. **W transposed**: row=contraction
  k, col=output c).
- **Bias** (P1): `b_load` + `b_flat` (N × 16-bit signed), once.
- **Activations**: stream columns on `col_valid`/`a_flat` when `col_ready`; `a_flat[k*DATA_W +:
  DATA_W] = A[k][m]`.
- **Results**: INT8 on `out_valid`/`out_data`, `out_ready` backpressure; order = (column outer,
  row inner): `y[0][0..N-1], y[1][0..N-1], …`.
- **Perf counters**: `perf_busy`, `perf_mac`, `perf_stall_act`, `perf_stall_bp` (cleared per `start`).

## 3. Arithmetic (the contract) — SPEC §2
`y[n,m] = clamp( round_half_up( (Σ_k W[n,k]·A[k,m]) + bias[n], shift ), relu?0:-128, 127 )`,
24-bit signed accumulation, round-half-up (`(t + (1<<(shift-1))) >>> shift`). Bit-exact to
`model/gemm_ref.py`.

## 4. Host tiling protocol (CENTERPIECE)
To compute `Y(Nout×M) = requant(W(Nout×K)·A(K×M) + bias)` on an ARRAY_N×ARRAY_N tile:
1. **Tile**: split Nout into ⌈Nout/ARRAY_N⌉ row-tiles (zero-pad the last), K into ⌈K/ARRAY_N⌉
   K-tiles, and M into chunks ≤ MAX_COLS. (`compiler/tiler.py` does this for the MLP.)
2. For each output **row-tile**:
   a. `start` with {num_cols=M_chunk, num_k_tiles, shift, relu, bias_en}; load bias once.
   b. For each **K-tile** (driven by `w_req`): load the N×N weight tile, then stream the M_chunk
      activation columns. The core clears the column accumulators on K-tile 0 and **accumulates**
      on the rest (K-accumulation); bias is added on the final K-tile.
   c. Drain N×M_chunk INT8 results; place into `Y[row-tile, M_chunk]`.
3. IRQ/`done` signals completion; read perf counters for utilization.

This is exactly what `dv/cocotb/coreio.run_descriptor` (one row-tile) and `tb_mnist`/`tiler`
(full MLP) implement — verified bit-exact, including the 8×8 MNIST demo (100/100 images).

## 5. Streaming format (SPI) — wrapper, P1/Phase 8
8-bit SPI frames: `{R/W, addr[6:0]}` then data byte(s). CSRs (PeakRDL from `regs/tensortile.rdl`):
control, descriptor regs / 4-deep queue (P1), status (busy/done/overflow/queue-occupancy),
IRQ enable/status, perf counters, `test_en`. (SPI→APB3 bridge + CSR block land with the top wrapper.)

## 6. Quantized-MLP demo flow
`model/mnist/train_quant.py` freezes INT8 weights (`mnist_int8.npz`, float 97.33% / INT8 96.67%);
`compiler/tiler.py` tiles them; the host streams per §4. Silicon classifies 8×8 digits bit-exact
vs `model/mlp_ref.py`. RP2040 firmware (Phase 8, `fw/`) will stream images and print classes +
perf counters.

## 7. Bring-up checklist
1. Power on, hold `rst_n` low ≥ a few cycles, release.
2. CSR sanity (read ID/status).
3. Single-tile GEMM (num_k_tiles=1, M=1), compare to `gemm_ref`.
4. K-accumulated GEMM (num_k_tiles>1).
5. MNIST MLP demo; dump perf counters (busy/MACs/util/stall-by-cause).
