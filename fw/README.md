# fw — RP2040 demo firmware (Phase 8)

Host driver + 8×8 MNIST demo for the TensorTile accelerator over SPI→CSR.

| file | purpose |
|------|---------|
| `tensortile.h` / `tensortile.c` | driver: CSR access, descriptor enqueue, weight/activation streaming, result/perf readback (CSR map = docs/INTEGRATION.md §5) |
| `mnist_demo.c` | tiles the 2-layer MLP onto ARRAY_N×ARRAY_N tiles and classifies 8×8 digits (M=1); prints class + perf counters |
| `mnist_weights.h` | frozen INT8 weights, generated: `PYTHONPATH=. python3 compiler/export.py` |

The demo flow mirrors the **verified** `dv/cocotb/tb_mnist` lockstep path (same tiling, same
arithmetic), so on a correctly-integrated SPI/CSR top it reproduces the silicon classifications.

**Status:** compile-clean C (`-Wall -Wextra`, checked against a mock HAL). **HW-untested** — it
targets the SPI/CSR top wrapper (integration pending) and real silicon. Provide the SPI HAL
(`tt_hal_*`) from the pico-sdk (`hardware/spi.h`) and a `demo_image[64]` source (UART or test ROM).

Build (host logic check): `gcc -Wall -std=c11 -I. tensortile.c mnist_demo.c your_hal.c`.
Build (RP2040): add these sources to a pico-sdk `CMakeLists.txt` with `pico_stdlib` + `hardware_spi`.
