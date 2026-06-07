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
