# dv/formal — SymbiYosys proofs (Phase 4)

`.sby` task files + properties for:
- **FIFO safety** — no overflow/underflow, data integrity, pointer correctness.
- **Control FSM** — deadlock freedom, only legal transitions.
- **Descriptor queue** — integrity (no drop/dup), occupancy bounds (P1).
- **Accumulator** — write-conflict freedom across columns / K-accumulation.

Bounded proofs must state their depth and why it suffices. Run via `make formal` (installs
yosys + sby from oss-cad-suite in Phase 4 / CI).

> Phase-0: placeholder only.
