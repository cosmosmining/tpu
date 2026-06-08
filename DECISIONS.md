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

## 2026-06-07 — Phase 3 DV closure

**[dv] Functional coverage = Python coverage model mapped to VPLAN (not SV covergroups).** Icarus
lacks practical covergroup support; verilator code-coverage is a separate axis. The Phase-3
functional coverage is a 26-bin model (`tb_regress.classify`) computed from the stimulus + golden
model, covering saturation (high/low), rounding ties (±) and shift regimes, most-negative operands
and the −128·−128 product, K-chain lengths, bias sign, M shapes, and output sign. Directed
adversarial descriptors pin the rare bins; random fills the rest. Result: **26/26 (100%)** over
**1,000,160 MACs / 3127 descriptors, 0 mismatches** (`dv/coverage_phase3.md`, 26.6 s).

**[dv] Shared driver `coreio.py`** factored out of `tb_core` so `tb_regress` reuses the exact
host protocol. `make sim` runs the fast levels (`-k "not regress"`); `make regress` runs the
≥1M-MAC campaign (REGRESS_MACS env, default 1e6); nightly CI runs the full campaign.

**[tooling] yosys 0.33 provisioned (apt).** Enables `make synth` for the area/flops-per-block
numbers the spec wants "from the first synthesis run." Added to setup_tools.sh tier.

## 2026-06-07 — Phase 4 formal

**[formal] Engine = yosys built-in `sat` + temporal induction (unbounded), not SymbiYosys.** sby
isn't in apt and needs an external SMT solver binary (z3 binary absent; only z3-python present).
yosys `sat -tempinduct` uses the built-in MiniSAT — zero extra deps, fully reproducible. Proofs
are **unbounded** (k-induction), not merely bounded.

**[formal] yosys `sat` IGNORES `$assume` cells (verified with a minimal testcase).** So input
constraints can't be expressed as in-RTL `assume` for this engine. Descriptor-input validity is
instead enforced **structurally** in the `dv/formal/fv_core.v` harness (num_cols∈[1..MAX_COLS],
num_k_tiles≥1 derived from free bits). The in-module `assume`s are retained (inert under `sat`)
for a future sby flow that honors them.

**[formal] Multiplier datapath deleted in the core proof (`delete t:$mul`).** The control/index
safety properties are independent of product values; freeing the datapath is a sound abstraction
and keeps the SAT instance tractable. arr_outv (control) comes from the valid-pipe FFs, untouched.

**[formal] Invariants had to be the reachable ones, not the naive bounds.** k-induction starts
from arbitrary assert-satisfying states, so `cout<=d_cols` / `dcol<MAX_COLS` were non-inductive
(an unreachable start could overshoot). Strengthened to the phase-scoped forms
`(S_STREAM⇒cout<d_cols)`, `(S_DRAIN⇒dcol<d_cols)` — the actual reachable invariants — which are
1-inductive. The RTL was already correct (it indexes `cout[CIDX-1:0]`); only the *properties*
needed tightening. Proven: FIFO safety; FSM legal-state; accumulator index + write-conflict freedom.

## 2026-06-07 — Phase 5 P1 (flagship demo, compiler, perf counters)

**[demo] End-to-end MNIST runs on the base core via Python-side tiling (`compiler/tiler.py`).**
Each MLP layer is split into ARRAY_N-row × ARRAY_N-K tiles (last row-tile zero-padded); per-tile
results from `tensortile_core` are assembled into the layer output. Since `run_descriptor` is
bit-exact to `quant_gemm` (proven in tb_core), the assembled result equals `mlp_ref`. Verified
**100/100 images bit-exact, 96.00% silicon accuracy** (`make demo`, `MNIST_IMAGES`). MNIST is
matrix-vector (M=1), so the base core suffices — no descriptor queue needed for the flagship.

**[perf] Performance counters added to the core** (busy, MACs=feeds·ARRAY_N², stall_act =
activation starvation, stall_bp = result backpressure), cleared per descriptor. `tb_perf` checks
MAC count exactly and that stall counters track injected starvation/backpressure (exact prediction
of stall cycles is left loose — cocotb drain entry/exit edges add ±2; the counters themselves are
exact in RTL). Exposed as core output ports; CSR readout lands with the SPI/CSR wrapper.

**[scope] Ping-pong weight double-buffer and the 4-deep descriptor queue remain.** They are pure-RTL
P1 differentiators (no new tools needed) tracked as remaining Phase-5 work, not skipped. The
area-fallback ladder treats both as reducible (descq 4→2; ping-pong only droppable with operator
approval), so the flagship/closure do not depend on them.

## 2026-06-07 — Phase 7 area DSE + Phase 6/7 tool reality

**[pd] sky130 PDK obtained via volare with an explicit version.** `volare ls-remote` / GitHub
releases API returns 403 in this environment, but `volare enable --pdk sky130 <hash>` (explicit
build) downloads the release assets fine. Gives `sky130_fd_sc_hd` tt liberty → real area numbers.

**[pd] LEAD WITH THE BAD NEWS: the core is area-tight.** Real sky130 synth: ARRAY_N=4, MAX_COLS=8
core = ~14–16k cells / **119,231 µm² / 93% util** vs the 4×2 die — **over the ≤70% target**, core
alone (before FIFOs/SPI/CSR). Cell *count* is within the 12–16k budget; cell *area* is the binding
constraint (16 multipliers + the MC=8 accumulator buffer dominate). Area-fallback knob: **MAX_COLS
8→2 ⇒ 73%** with no effect on the M=1 MNIST demo. ARRAY_N=3 = 49% util but breaks K-divisibility
for the 64/32-wide MLP. Recommendation: ARRAY_N=4 + MAX_COLS=2 (+ possible ACC_W=20) or a larger
tile — **operator selects the tapeout point** (pnr/dse_report.md). Peak 0.8 GMAC/s @ 50 MHz target.

**[pd] OpenROAD / OpenSTA / Fault are NOT installable in this ephemeral env** (not in apt; OpenLane2
is a pip orchestrator but needs the OpenROAD binary via nix/container, ~GB). Per the spec's
"uninstallable → CI + DECISIONS entry": Fmax (OpenSTA), placement utilization + **GDS** (OpenROAD/
LibreLane), and **ATPG** (Fault, Phase 6) are deferred to CI. `gds.yml` is wired for the official
Tiny Tapeout GDS Action (manual/tag-gated until the design point + info.yaml pins are frozen).
This is honest deferral, not a silent skip — the area DSE above is the real, in-env PD result.

**[status] Phases done in-env: 0–5 fully + Phase 7 area-DSE. Remaining: Phase 5 ping-pong/descq
(pure RTL), Phase 6 ATPG (Fault/CI), Phase 7 Fmax+GDS (OpenSTA/OpenROAD/CI), Phase 8 release docs +
RP2040 fw.** No quality gate was lowered or faked; tool-blocked items are explicitly CI-deferred.

## 2026-06-07 — Phase 5 ping-pong: evaluated, intentionally NOT shipped

**[arch] Ping-pong weight double-buffer evaluated and reverted (engineering call).** I implemented
the full dual-bank array (`PINGPONG` param) + an overlapped core FSM (load next K-tile into the
inactive bank during streaming, swap at the tile boundary). Findings:
1. **No benefit for this microarchitecture.** The core's weight load is a **single-cycle parallel**
   load (`w_load`+`w_flat`), so the inter-K-tile "bubble" ping-pong hides is ~1 cycle — negligible.
   Ping-pong pays off only when weight load is *multi-cycle* (e.g., a serial shift-chain). It isn't
   here.
2. **Area-negative.** A second N×N weight bank (+128 ff + muxing) *increases* area, and the sky130
   DSE already puts the core over the ≤70% util target (ERRATA E1). Wrong direction.
3. The dual-bank + clean swap path was verified bit-exact (tb_core with PINGPONG=1, S_WAITW load),
   but the *load-during-stream overlap* path had a residual mismatch I did not fully root-cause; per
   the immutable quality bar (ship only verified, bit-exact RTL) I reverted rather than ship it.

**Conclusion:** the verified design keeps the single-bank array + the (already-shipped) descriptor
queue. Ping-pong is the documented next step **only if** the weight-load path is changed to
multi-cycle (shift-chain), at which point the latency it hides becomes real and the area trade is
re-evaluated against the chosen DSE point. The dual-bank work is recoverable from git history.
