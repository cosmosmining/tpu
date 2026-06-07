# ERRATA — TensorTile

Known issues, limitations, and deviations from spec, with workarounds and target fix phase.
Newest at the bottom. (Honesty over polish — see CLAUDE.md quality bars.)

| date | id | severity | description | workaround | fix target |
|------|----|----------|-------------|------------|-----------|
| 2026-06-07 | E1 | **high** | At ARRAY_N=4, MAX_COLS=8 the compute core is ~93% util of the 4×2 die (over the ≤70% target), core-only (before FIFOs/SPI). | Area-fallback: MAX_COLS 8→2 (core 73%, no MNIST impact), ±ACC_W 20, or request a larger tile. | Phase 7 (operator picks point) |
| 2026-06-07 | E2 | med | Post-route **Fmax / WNS** not yet closed (OpenSTA not installable in-env). | Synthesizes; target 50 MHz. Run STA in CI. | Phase 7 / CI |
| 2026-06-07 | E3 | med | **GDS + true placement utilization** not generated (OpenROAD/LibreLane not installable in-env). | `gds.yml` wired for the official TT GDS Action (manual/tag). | Phase 7 / CI |
| 2026-06-07 | E4 | med | **Scan + ATPG** not inserted/measured (Fault not installable in-env). | Pin map reserves scan under `test_en`; run in CI. | Phase 6 / CI |
| 2026-06-07 | E5 | low | **SPI/CSR top wrapper** not yet integrated; `tt_um_tensortile` is an interface stub. Compute path verified at the `tensortile_engine` level; firmware targets the documented CSR map but is HW-untested. | Drive the verified engine directly (as DV does). | next (top integration) |
| 2026-06-07 | E6 | low | **Ping-pong** weight double-buffer not implemented (adds a weight bank → more area, counter to E1). | None needed; weight load is on-demand per K-tile via `w_req`. | deferred (area tradeoff; operator approval per fallback ladder) |
| 2026-06-07 | E7 | info | Formal uses yosys `sat` (k-induction), which ignores `$assume`; input constraints applied structurally in `dv/formal/fv_core.v`. Proofs are unbounded and sound. | — | n/a |
| 2026-06-07 | E8 | info | sky130 area measured against the `sky130B` `fd_sc_hd` liberty (volare default for the fetched build); digital std cells are identical to sky130A for area estimation. | — | n/a |
