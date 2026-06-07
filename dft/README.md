# dft — scan + ATPG (Phase 6)

Fault scan-chain insertion and ATPG. Test mode is muxed onto `uio` under a test-enable CSR bit.
Target ≥95% stuck-at coverage on scanned logic — **report the real number**. Functional
regression must re-pass with scan inserted. Run via `make dft`.

> Phase-0: placeholder only.
