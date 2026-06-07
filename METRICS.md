# METRICS — TensorTile (append-only)

Each row is one measurement point. **Append only — never edit or delete past rows.**
Rows are added by `scripts/metrics.py` (parses tool logs → `summary.json` → a row here) from
Phase 2 (first synth) onward; earlier rows are recorded by hand.

Columns:
- **date** — YYYY-MM-DD
- **commit** — short SHA the numbers describe
- **phase** — pipeline phase
- **func_cov** — functional coverage % (DV)
- **macs** — MAC operations exercised in regression
- **cells / area** — std-cell count / um² (per-block detail lives in synth/ reports)
- **WNS** — worst negative slack (ns) at stated corner/freq
- **util** — back-to-back-tile MAC utilization % (or place utilization for PD rows)
- **atpg** — stuck-at coverage %
- **notes**

| date | commit | phase | func_cov | macs | cells / area | WNS | util | atpg | notes |
|------|--------|-------|----------|------|--------------|-----|------|------|-------|
| 2026-06-07 | scaffold | 0 | n/a | n/a | n/a | n/a | n/a | n/a | Phase 0 scaffold; `make smoke` green (known-answer INT8 matmul + `tt_um_tensortile` stub compiled w/ iverilog+verilator). No synth/DV/PD yet. |
