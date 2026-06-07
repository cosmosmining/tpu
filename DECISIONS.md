# DECISIONS — TensorTile

Dated, append-only log of every non-obvious decision and its rationale.
Newest at the bottom. Format: `YYYY-MM-DD — [AREA] decision — rationale`.

---

## 2026-06-07 — Phase 0 scaffold

**[layout] Repo root *is* the TensorTile project; no extra `tensortile/` nesting.**
Spec §3 draws `tensortile/` as the top folder, but this is the `cosmosmining/tpu` repo whose
purpose is exactly TensorTile. Nesting under `tpu/tensortile/` would be redundant and would
break the Tiny Tapeout convention of project files at repo root. All §3 paths are created at
the repo root.

**[tooling] Tool provisioning tiers.**
- REQUIRED (pip, installed locally): `numpy cocotb cocotb-bus pytest`.
- LOCAL (apt, installed locally, best-effort): `iverilog verilator`.
- CI / later-phase / release-binary (not installed in Phase 0): `yosys`, `sby` (SymbiYosys),
  `verible` (Google release binary, not in apt), `openroad`/`librelane` (heavy), `fault`
  (DFT/ATPG), `peakrdl` (pip, but a Phase-1 dependency — deferred to keep Phase 0 lean).
Rationale: maximize *real* local checks for Phase 0 (`smoke`, `lint`) while not paying the cost
of a ~1 GB OSS-CAD-Suite download this early. Heavy tools are provisioned on demand in the phase
that first needs them and in CI. Nothing is silently skipped — `make` targets and `setup_tools.sh`
print a tool matrix marking each tool RUN or MISSING→CI/later.
Observed Phase-0 versions: verilator 5.020, iverilog (Debian), numpy 2.4.6, cocotb 2.0.1,
pytest 9.0.3.

**[rtl] Phase-0 `tt_um_tensortile` is an interface-only stub (no design logic).**
Engineering standard #1 forbids design RTL before SPEC.md is frozen. To give `make smoke`/`make
lint` something real to compile and to lock the TT pin interface early, `rtl/tt_top/
tt_um_tensortile.v` defines the standard TT ports and drives all outputs to a safe reset state
(zeros, `uio_oe=0`) with **no functional datapath**. It is explicitly marked as a Phase-0
scaffold placeholder to be replaced in Phase 2 after SPEC freeze. This is scaffolding, not the
design, so it does not violate "no RTL before spec."

**[build] Unimplemented Makefile targets exit 0 with an explicit notice.**
`sim/regress/formal/cov/synth/dft/harden/sweep/predict` print `Phase N — not yet implemented`
and exit 0 in Phase 0. They are documented scaffold placeholders (here + CLAUDE.md), not silent
skips, and keep CI green. They will be implemented in their respective phases; the immutable
quality-gate rule (never fake a result to pass a gate) is unaffected — Phase 0's only gate is
`make smoke`, which does real work.

**[ci] `gds.yml` triggers on `workflow_dispatch` + tags only (not push/PR).**
The official Tiny Tapeout GDS Action requires a complete, valid TT project (real `info.yaml`
pins, hardened sources). Running it on every push during Phases 0–6 would redden `main` for no
reason. It is wired now but gated to manual/tag runs until Phase 7. `lint/test/formal/nightly`
run on push/PR and must stay green.

**[ci] SessionStart hook added (ephemeral-container provisioning).**
Containers are reclaimed between sessions and cloned fresh, so EDA tools vanish each session.
`.claude/hooks/session-start.sh` re-runs `scripts/setup_tools.sh` on session start (web only,
guarded by `$CLAUDE_CODE_REMOTE`). Synchronous mode for the first iteration (guarantees tools
are ready before the agent acts, at the cost of slightly slower startup); can switch to async
later if startup latency matters.

**[tt] `info.yaml` is a stub with pins marked TBD.**
The TT project metadata file is created now for completeness, but pin assignments depend on the
SPI/CSR pinout defined in SPEC.md (Phase 1). Pins are placeholders until then; reconciled with
the spec §3 tree during Phase 7 hardening.

## 2026-06-07 — Phase 1 spec + golden model

**[arithmetic] Requant rounding = round-half-up (operator-frozen).** `(t + 2^(s-1)) >> s` with
arithmetic shift; ties toward +∞; `s=0` exact passthrough; then clamp to INT8 (ReLU ⇒ lower
bound 0). Operator chose this over round-half-to-even / away-from-zero / truncate (cheapest HW,
classic TPU-style, deterministic). This is THE contract — SPEC §2, `gemm_ref.py`, tests all agree.

**[arithmetic] 24-bit accumulator is non-saturating; overflow is out-of-spec.** Bit-exactness +
K-tiling carry favor a plain two's-complement accumulator sized to not overflow; the K bound
(≤511 adversarial terms) is documented (SPEC §2.3) and enforced by `quant_gemm_ktiled`
(raises OverflowError). "Saturation at every stage" applies to the requant→INT8 + ReLU stages.

**[arithmetic] Output path order:** `acc → +bias(final K-tile) → round-half-up shift → clamp(lo,127)`
where `lo = 0 if relu else -128`. Saturation and ReLU folded into one clamp (order-independent for
the shared upper bound). Bias added once, on the final K-tile.

**[quant] Power-of-two-only quantization scheme.** All scales are 2^e so on-chip requant is a pure
arithmetic shift (no requant multiplier). Inputs: pixel/16 ∈[0,1] → INT8 at scale 2^-7. Weights:
per-tensor symmetric INT8, scale 2^ceil(log2(max|W|/127)). Bias: accumulator-domain, 16-bit.
Requant shifts chosen from the training-set max |acc| to fill INT8 range. Frozen to
`model/mnist/mnist_int8.npz` (committed).

**[demo] MNIST 8×8 via sklearn `load_digits` (offline, no network).** Hidden=32, seed=0. Reported:
**float 97.33% / INT8 96.67%** test accuracy (bit-exact integer path) — 0.66% quant drop. The
INT8 number is the silicon target. (sklearn added to requirements; install was transient-flaky
once, succeeded on retry.)

**[pinmap] SPI-slave pinout defined (SPEC §8) so Phase 2 RTL can proceed.** SCLK/CSn/MOSI on
`ui_in[2:0]`; MISO/IRQ/busy/done on `uo_out[3:0]`; `uio` reserved (inputs, `uio_oe=0`) in P0,
reserved for scan muxing under `test_en` in Phase 6. Normally a "stop and ask" item, but the
operator directed proceeding through phases; pinout chosen conventionally and logged here.

## 2026-06-07 — Phase 2 P0 RTL + lockstep

**[arch] Systolic dataflow = activation-broadcast-per-row + registered partial sums down columns,
with per-row input skew (lane k delayed k cycles).** This is a legitimate weight-stationary
systolic array faithful to SPEC §3 (weights stationary in PEs, row skew, psum flows down,
1 result column/cycle after an ARRAY_N fill latency). Activations are broadcast across the columns
within a row (fanout ARRAY_N=4, small) rather than flowing horizontally register-by-register —
this keeps the design compact and easy to verify while preserving the architecture and the exact
arithmetic. Verified bit-exact vs `gemm_ref` (tb_array: single-tile + backpressure).

**[arch] Weight mapping `wmem[k][c] = W[c][k]` (array stores W transposed).** Contraction index k
on array rows, output index c on array columns, so column c's bottom accumulator yields
`sum_k W[c,k]*a[k]`. Documented in `tt_mac_array.v` and the host tiling protocol.

**[arch] K-accumulation via an `ACC[ARRAY_N][MAX_COLS]` buffer; `MAX_COLS` parameter (default 8).**
The host re-streams the same activation columns per K-tile (reloading weights each K-tile); the
core accumulates per-(row,col). `num_cols ≤ MAX_COLS`; larger M is host-tiled. MNIST inference is
M=1 (matrix-vector), so this bound is comfortable; it caps accumulator flops for area. Faithful to
the no-SRAM, flops-only constraint. Bit-exact vs `quant_gemm`/`quant_gemm_ktiled` (tb_core).

**[arch] `w_req` weight-request handshake.** Core raises `w_req` in S_LOADW; the host supplies the
K-tile's weights (parallel `w_load`/`w_flat`; shift-chain serialization is a wrapper concern).
Clean host/core sync without exposing internal state.

**[dv] cocotb 2.0.x runner flow.** `cocotb_tools.runner.get_runner` + Icarus; `Clock(..., unit=)`;
`timescale=("1ns","1ps")` required (else Icarus 1s precision rejects a 10ns clock). Benches use
the ReadOnly-sample → drive → edge pattern; `make sim` runs all four levels. Bench protocol note:
wait for `busy==0` before issuing `start` (the core needs 1-2 cycles to return to IDLE after DONE).

**[dv] No `row` level module.** The array composes PEs directly per SPEC §3; a separate `row.v`
added no verification value over the PE + array benches, so the ladder is PE → array → core.
