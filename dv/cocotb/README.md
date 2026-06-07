# dv/cocotb — lockstep benches (Phase 2+)

cocotb testbenches comparing RTL against the NumPy golden model on identical stimulus, built
bottom-up: `test_pe.py` → `test_row.py` → `test_array.py` → `test_core.py`, then directed +
constrained-random campaigns and the MNIST demo. Run via `make sim` / `make regress`.

Notes:
- Bit-exact comparison only — any mismatch is a bug (never a tolerance).
- cocotb is **2.0.x** here (API differs from 1.x); verify bench idioms against 2.x docs.
- Runs under iverilog and/or verilator (both provisioned locally).

> Phase-0: placeholder only.
