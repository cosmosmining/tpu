---
description: Run a level's cocotb lockstep bench (RTL vs NumPy model) and report bit-exactness.
argument-hint: "pe | row | array | core (default: all)"
allowed-tools: Bash(make:*), Bash(python3:*), Read
---
Run the cocotb lockstep bench(es) comparing RTL against the NumPy golden model on identical
stimulus. Level from `$ARGUMENTS` (one of `pe`, `row`, `array`, `core`); default all.

1. Run `make sim` (optionally scoped to the requested level, e.g. `make sim LEVEL=$1`).
2. For every output, confirm RTL == model **to the bit**. Any mismatch is a bug — never a
   tolerance. Report the first mismatch with the exact RTL vs model values and the stimulus.
3. Summarize: which levels ran, cycles/vectors exercised, pass/fail.

Bit-exactness is the product (CLAUDE.md quality bars). If the model itself looks wrong, STOP —
do not edit the golden model to make RTL pass; that needs a SPEC.md citation + DECISIONS.md entry.

If `make sim` isn't live yet, report the Phase-N placeholder notice plainly.
