# VPLAN — TensorTile verification plan

> Phase-0 skeleton. Phase 1 populates the feature→test→coverage matrix; Phase 3 closes it
> (≥95% functional coverage, ≥1M MACs lockstep-clean). Every SPEC feature MUST map to at least
> one named test and one named functional coverage point.

## Methodology
- **Lockstep at every level**: PE, row, array, full core each get a cocotb bench comparing RTL
  against the NumPy golden model on identical stimulus. Any bit mismatch = bug.
- Directed tests for edge cases; constrained-random for breadth; coverage closes the gap.
- Adversarial stimulus: saturation extremes, most-negative operands (−128), rounding ties.

## Feature → Test → Coverage (TODO: fill in Phase 1, one row per SPEC feature)
| ID | SPEC ref | Feature | Test(s) | Coverage point(s) | Status |
|----|----------|---------|---------|-------------------|--------|
| F-ACC | §2 | 24b signed accumulation, no overflow on demo workload | `test_pe_mac`, `test_array_gemm` | acc range bins, overflow-guard | TODO |
| F-SAT | §2 | INT8 saturation at requant | `test_requant_sat` | sat-high / sat-low events per stage | TODO |
| F-RND | §2 | requant rounding rule incl. ties | `test_requant_round` | tie-up / tie-down / boundary bins | TODO |
| F-NEG | §2 | most-negative operand handling | `test_adversarial_neg` | −128 operand cross | TODO |
| F-RELU | §2 | saturating ReLU enable | `test_relu` | relu on/off × sign | TODO |
| F-KACC | §4 | K-tiling multi-tile accumulation | `test_k_accumulation` | K-chain length bins | TODO |
| F-FIFO | §3 | act-in / result-out FIFO boundaries | `test_fifo_bounds` | empty/full/wrap | TODO |
| F-DESC | §4 | descriptor decode (single, P0) | `test_descriptor` | each field min/max | TODO |
| F-BIAS | §2 (P1) | 16b bias add | `test_bias` | bias sign × sat | TODO |
| F-DQ | §4 (P1) | 4-deep descriptor queue drain | `test_desc_queue` | queue occupancy 0..4 | TODO |
| F-PP | §3 (P1) | ping-pong weight switchover | `test_pingpong_race` | switch under load | TODO |
| F-PERF | §4 (P1) | perf counters vs model | `test_perf_counters` | stall-cause bins | TODO |
| F-MNIST | demo | end-to-end MNIST ≥100 imgs bit-exact | `test_mnist_demo` | per-class coverage | TODO |

## Coverage targets (immutable)
- Functional coverage ≥ **95%** (Phase 3 gate).
- ≥ **1,000,000** MAC operations across shapes/adversarial values, zero mismatches.
- MNIST demo subset bit-exact end-to-end.

## Formal plan (Phase 4 — see `dv/formal/`)
- FIFO safety (no overflow/underflow, data integrity), control-FSM deadlock freedom + legal
  transitions, descriptor-queue integrity, accumulator write-conflict freedom. Bounded proofs
  state depth + justification.
