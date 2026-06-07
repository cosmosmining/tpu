# dv/formal — formal proofs (Phase 4)

Engine: **yosys built-in `sat` with temporal induction** (`-tempinduct` ⇒ unbounded safety
proofs). No external SMT solver required. `make formal` runs both proofs; CI installs yosys.

> Note: yosys `sat` ignores `$assume` cells, so descriptor-input constraints are applied
> **structurally** in `fv_core.v` rather than via `assume`. The in-module `assume`s remain for a
> future SymbiYosys flow (which honors them). See DECISIONS.md (2026-06-07, Phase 4).

## Proven properties
**`prove_fifo.ys`** — `tt_fifo` (WIDTH=8, DEPTH=8), k-induction:
- counter never overflows (`count <= DEPTH`); pointers in range;
- `empty`/`full` flags consistent with `count`;
- never push when full / pop when empty (no overflow/underflow).

**`prove_core.ys`** — `tensortile_core` via `fv_core` harness (multiplier datapath deleted as a
sound abstraction for the control properties), k-induction:
- FSM never enters an illegal state (`state <= S_DONE`); legal transitions only;
- accumulator indices always in range: `cout < d_cols` (write, while streaming),
  `dcol < d_cols` (read, while draining), `drow < ARRAY_N`, `d_cols <= MAX_COLS`;
- outputs strictly confined to the drain phase (`out_valid ⇔ state==S_DRAIN`) ⇒ accumulator
  reads and writes never collide (write-conflict freedom).

Descriptor-queue integrity (P1) is added in Phase 5 when the queue is implemented.
