# fw — RP2040 demo firmware (Phase 8)

C firmware for the Tiny Tapeout RP2040 controller that:
- streams quantized weights + activations to TensorTile over SPI,
- runs the 8×8 MNIST MLP demo through the silicon,
- prints predicted classes and dumps performance counters (busy/MACs/util/stall-by-cause).

Phase-0: placeholder only. Implemented in Phase 8 once the silicon interface is frozen.
