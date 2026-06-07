# compiler — quantized MLP → tiled descriptors + data streams (P1 / Phase 5)

Python tool that converts a quantized MLP (`.npz`; ONNX import optional) into:
- a sequence of tile **descriptors** (per SPEC §4) implementing the host tiling protocol, and
- the matching **weight / activation data streams** for SPI delivery.

Drives the end-to-end MNIST demo in cocotb (≥100 images, bit-exact vs `model/mlp_ref.py`) and,
in Phase 8, the RP2040 firmware. Phase-0: placeholder only.
