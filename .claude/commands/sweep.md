---
description: Run the Phase-7 DSE sweep and produce a Pareto table (area, Fmax, MACs/s, MACs/s/mm²).
argument-hint: "[ARRAY_N list] [clk list] (optional)"
allowed-tools: Bash(make:*), Read
---
Drive the parallel design-space exploration (this chip's signature phase).

1. Run `make sweep` over the grid: ARRAY_N {3,4} × pipelining options × clock target × placement
   density (parallelism is free — fan out). Narrow with `$ARGUMENTS` if given.
2. Collect per-point: area, Fmax, MACs/cycle, MACs/s, MACs/s/mm², utilization, WNS.
3. Emit a **Pareto table** into METRICS.md and identify the Pareto-optimal points.
4. Present the table and a recommendation, but **the operator picks the tapeout point** — do not
   choose it yourself. Flag any point violating WNS ≥ 0 or util ≤ 70%.

If sweep isn't live yet (pre-Phase 7), report the placeholder notice plainly.
