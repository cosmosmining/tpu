---
description: Run the constrained-random regression and summarize pass/fail + coverage + MAC count.
argument-hint: "[seed-count | shape filter] (optional)"
allowed-tools: Bash(make:*), Bash(python3:*), Read
---
Run the TensorTile regression and report **evidence, not adjectives**.

1. Run `make regress` (Phase 3+: constrained-random shapes/data, ≥1M MACs). Pass through any
   filter in `$ARGUMENTS` (e.g. a seed count or shape selector) if supported.
2. Parse the result: total MACs exercised, mismatches (must be 0), functional coverage %.
3. If `make cov` is available, run it and include the coverage breakdown per VPLAN point.
4. Report: `<N> MACs lockstep-clean, coverage <X>%, <mismatches> mismatches`. If anything
   failed, **lead with the failure** and the first mismatching case (RTL vs model values).
5. Append a METRICS.md row via `make metrics` if a summary.json was produced.

If this phase isn't live yet, say so plainly (the target prints a Phase-N placeholder notice).
