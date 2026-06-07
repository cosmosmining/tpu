# pnr — hardening + DSE (Phase 7)

LibreLane / OpenROAD-flow-scripts configs and the parallel DSE sweep harness:
ARRAY_N {3,4} × pipelining × clock target × placement density → Pareto table (area, Fmax,
MACs/s, MACs/s/mm²) in METRICS.md. The operator selects the tapeout point. TT precheck/GDS goes
green via the official TT GitHub Action. Run via `make harden` / `make sweep`.

> Phase-0: placeholder only.
