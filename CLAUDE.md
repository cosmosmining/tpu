# CLAUDE.md — TensorTile flow brain

> Weight-stationary INT8 systolic GEMM accelerator IP for Tiny Tapeout (TTSKY26c, sky130A).
> This file is the operational map. **Read this + STATUS.md + DECISIONS.md + last 10 lines of
> METRICS.md at the start of every session, before doing anything.**

## What this chip is
A TPU-v1-style **weight-stationary INT8 systolic GEMM tile** with on-chip per-tensor
requantization. Weights are preloaded and held in the PE array; activations stream in with
row skew; partial sums flow down column accumulators that support multi-tile K-accumulation so
a host can tile arbitrarily large GEMMs. Outputs pass through `{bias → requant shift →
saturating ReLU}` into an output FIFO. Flagship demo: a 2-layer quantized MLP classifying
8×8 MNIST digits, **bit-exact** between silicon and NumPy.

- Top module: `tt_um_tensortile` (standard TT interface). Single clock, target **50 MHz**.
- Fully parametric: `ARRAY_N` (4), `DATA_W` (8), `ACC_W` (24). **Never hardcode these.**
- All storage is flops (no SRAM macros). FIFOs ≤ 16 deep. Sync active-low reset, no latches,
  no comb loops, single clock domain.

## Repository map
| Path | Purpose |
|------|---------|
| `CLAUDE.md` | this file — flow brain |
| `STATUS.md` | current phase, last results, next actions (update every session) |
| `DECISIONS.md` | dated log of every non-obvious decision + rationale |
| `METRICS.md` | append-only: date, commit, coverage, area/block, WNS, util, ATPG% |
| `PREDICTIONS.md` | pre-registered silicon predictions (frozen at tapeout, Phase 7) |
| `docs/SPEC.md` | arithmetic definition, dataflow, descriptor format, tiling protocol |
| `docs/VPLAN.md` | feature → test → coverage mapping |
| `docs/INTEGRATION.md` | CSR map, host tiling protocol, streaming format, bring-up |
| `docs/ERRATA.md` | known issues |
| `model/gemm_ref.py` | bit-exact quantized GEMM reference + unit tests |
| `model/mlp_ref.py` | 2-layer quantized MLP reference |
| `model/mnist/` | offline train/quant script + frozen committed weights |
| `compiler/` | quantized MLP (npz/ONNX) → tiled descriptors + data streams |
| `rtl/core/` | `tensortile_core` + APB3 CSR interface (parametric) |
| `rtl/tt_top/` | `tt_um_tensortile` wrapper + SPI→APB bridge |
| `regs/tensortile.rdl` | SystemRDL: control, descriptor queue, status, perf counters |
| `dv/cocotb/` | PE/row/array/core lockstep benches (directed + constrained-random) |
| `dv/formal/` | SymbiYosys `.sby` + properties |
| `dft/ synth/ pnr/` | Fault scripts; Yosys; LibreLane/ORFS configs + DSE harness |
| `fw/` | RP2040 firmware: weight/activation streaming, MNIST demo, perf dump |
| `scripts/metrics.py` | log parsing → summary.json → METRICS.md row |
| `scripts/setup_tools.sh` | idempotent tool provisioner (pip + apt; CI for the rest) |

## Build / test / harden commands (Makefile targets)
| Target | Does | Phase it goes live |
|--------|------|--------------------|
| `make setup` | provision tools (pip + apt; idempotent) | 0 |
| `make smoke` | **gate of Phase 0** — env + known-answer matmul + compile top stub | 0 |
| `make lint` | `verilator --lint-only` (+ verible if present); zero errors required | 0 (real) |
| `make sim` | cocotb lockstep benches | 2 |
| `make regress` | full constrained-random regression (≥1M MACs) | 3 |
| `make formal` | SymbiYosys proofs (FIFO/FSM/descq/accumulator) | 4 |
| `make cov` | functional + code coverage report | 3 |
| `make synth` | Yosys synth + area/flop report → METRICS.md | 2+ |
| `make dft` | Fault scan insertion + ATPG | 6 |
| `make harden` | LibreLane/ORFS single-point hardening | 7 |
| `make sweep` | parallel DSE (ARRAY_N × pipelining × clk × density) | 7 |
| `make predict` | freeze PREDICTIONS.md from STA/area | 7 |
| `make clean` | remove build artifacts | 0 |

Targets not yet live print a clear `Phase N — not yet implemented` notice and exit 0 (scaffold
placeholders, logged in DECISIONS.md). They are **not** silent skips.

## Quality bars (immutable — never lower to pass a gate)
- **Bit-exactness is the product.** NumPy golden model defines the arithmetic. Silicon = RTL =
  model, to the bit, on every output. Any mismatch is a bug. **Never edit the golden model to
  make RTL pass** — model changes require a SPEC.md citation + DECISIONS.md entry.
- Lint-clean at every commit. Waivers need an inline comment + DECISIONS.md entry.
- ≥95% functional coverage (Phase 3), ≥1M random MACs lockstep-clean.
- ≥95% stuck-at ATPG coverage on scanned logic (Phase 6) — report the real number.
- f_clk ≥ 50 MHz post-route, WNS ≥ 0 at tt corner (Phase 7).
- ≤70% utilization; track area + flops per block in METRICS.md from first synth.
- Report measured numbers, not adjectives. If a result is bad, lead with it.

## Tooling reality
- Installed locally where possible: numpy, cocotb, pytest (pip); iverilog, verilator (apt).
- CI / later-phase / release-binary: yosys, sby, verible, openroad/librelane, fault, peakrdl.
- Detect-then-install; anything uninstallable → CI + a DECISIONS.md entry. Never silent-skip.
- Containers are ephemeral: `.claude/hooks/session-start.sh` re-provisions every session.

## Working agreement
- One phase per instruction; stop at every gate with a report (built / evidence / metrics /
  risks / proposed next). Do not start the next phase until the operator says "continue."
- Conventional commits, one logical change each. Never commit failing lint or broken smoke.
- When blocked: smallest reasonable assumption → DECISIONS.md → continue, **unless** it touches
  the arithmetic definition, quality gates, area >70%, parameters, or the pin map — then stop
  and ask exactly one focused question.
- Develop on branch `claude/inspiring-allen-bw0cx`. Never push elsewhere without permission.
