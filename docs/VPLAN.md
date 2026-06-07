# VPLAN — TensorTile verification plan

> Phase-0 skeleton. Phase 1 populates the feature→test→coverage matrix; Phase 3 closes it
> (≥95% functional coverage, ≥1M MACs lockstep-clean). Every SPEC feature MUST map to at least
> one named test and one named functional coverage point.

## Methodology
- **Lockstep at every level**: PE, row, array, full core each get a cocotb bench comparing RTL
  against the NumPy golden model on identical stimulus. Any bit mismatch = bug.
- Directed tests for edge cases; constrained-random for breadth; coverage closes the gap.
- Adversarial stimulus: saturation extremes, most-negative operands (−128), rounding ties.

## Feature → Test → Coverage (status as of Phase 3)
Tests: model = `model/test_*.py`; RTL benches = `dv/cocotb/tb_*.py`; cov bins = `tb_regress.py`.
| ID | SPEC ref | Feature | Test(s) | Coverage bin(s) | Status |
|----|----------|---------|---------|-----------------|--------|
| F-ACC | §2 | 24b signed accumulation, no overflow on demo workload | `test_gemm_ref`, `tb_array`, `tb_core` | (kacc_*), overflow-guard test | ✅ RTL+cov |
| F-SAT | §2 | INT8 saturation at requant | `tb_requant`, `tb_regress` | sat_high, sat_low | ✅ RTL+cov |
| F-RND | §2 | requant rounding rule incl. ties | `test_gemm_ref`, `tb_requant` | tie_pos, tie_neg, nontie, shift_zero/small/large | ✅ RTL+cov |
| F-NEG | §2 | most-negative operand handling | `test_gemm_ref`, `tb_regress` | op_neg128_w, op_neg128_a, product_max | ✅ RTL+cov |
| F-RELU | §2 | saturating ReLU enable | `tb_requant`, `tb_core` | relu_on, relu_off | ✅ RTL+cov |
| F-KACC | §4 | K-tiling multi-tile accumulation | `tb_core`, `test_mlp_ref` | kacc_1, kacc_2_4, kacc_5plus | ✅ RTL+cov |
| F-FIFO | §3 | act-in / result-out FIFO boundaries | `tb_fifo` | empty/full/wrap (model-checked) | ✅ RTL |
| F-DESC | §4 | descriptor decode (single, P0) | `tb_core` (num_cols/k_tiles/shift) | M_1/M_mid/M_max | ✅ RTL |
| F-BIAS | §2 (P1) | 16b bias add | `tb_requant`, `tb_core` | bias_on/off/pos/neg | ✅ RTL+cov |
| F-DQ | §4 (P1) | 4-deep descriptor queue drain | `test_desc_queue` | queue occupancy 0..4 | Phase 5 |
| F-PP | §3 (P1) | ping-pong weight switchover | `test_pingpong_race` | switch under load | Phase 5 |
| F-PERF | §4 (P1) | perf counters vs model | `test_perf_counters` | stall-cause bins | Phase 5 |
| F-MNIST | demo | end-to-end MNIST bit-exact (model) | `test_mlp_ref` (96.67%) | per-class | ✅ model; RTL demo Phase 5 |

Phase-3 regression: see `dv/coverage_phase3.md` (generated) — 26/26 functional bins, ≥1M MACs,
0 mismatches.

## Coverage targets (immutable)
- Functional coverage ≥ **95%** (Phase 3 gate).
- ≥ **1,000,000** MAC operations across shapes/adversarial values, zero mismatches.
- MNIST demo subset bit-exact end-to-end.

## Formal plan (Phase 4 — see `dv/formal/`)
- FIFO safety (no overflow/underflow, data integrity), control-FSM deadlock freedom + legal
  transitions, descriptor-queue integrity, accumulator write-conflict freedom. Bounded proofs
  state depth + justification.
