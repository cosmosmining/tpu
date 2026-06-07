---
description: Synthesize + run STA and report Fmax / WNS / area / flops at the tt corner.
argument-hint: "[clock target MHz] (default 50)"
allowed-tools: Bash(make:*), Read
---
Report timing/area **measured numbers**.

1. Run `make synth` (Yosys area/flop report) and, when available, the STA step (OpenSTA).
2. Extract at the tt corner: **Fmax**, **WNS** at the target clock (`$ARGUMENTS` MHz, default 50),
   cell count, flop count, and area per block.
3. Check against the quality bars: f_clk ≥ 50 MHz post-route, WNS ≥ 0; utilization ≤ 70%.
4. Report e.g. `WNS +0.18 ns @ 50 MHz tt, 12.4k cells, util 64%`. If WNS < 0 or util > 70%,
   **lead with it** and propose the area-fallback-ladder step (CLAUDE.md / SPEC §9).
5. Append a METRICS.md row via `make metrics`.

If synth/STA aren't live yet, report the Phase-N placeholder notice plainly.
