# model/mnist — offline MNIST training + quantization (Phase 1)

Phase 1 adds here:
- `train_quant.py` — trains a small 2-layer MLP on 8×8 MNIST (sklearn `load_digits`, no network
  dependency), post-training-quantizes it to INT8 per the frozen SPEC §2 arithmetic, and emits
  **frozen weights committed to this directory** (`mnist_int8.npz`).
- Reported reference accuracy (float vs quantized) recorded in STATUS.md / the Phase-1 gate.

These frozen weights drive `model/mlp_ref.py`, the `compiler/`, and the end-to-end MNIST demo
(≥100 images, bit-exact silicon vs model).

> Phase-0: directory placeholder only — no weights yet.
