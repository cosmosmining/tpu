# synth — Yosys synthesis (Phase 2+)

Yosys scripts that synthesize `tensortile_core` / `tt_um_tensortile` to sky130 cells and emit an
**area + flop report per block** (multipliers dominate — track from the first run). Output feeds
`scripts/metrics.py` → METRICS.md. Run via `make synth`.

> Phase-0: placeholder only.
