"""
mlp_ref.py — 2-layer quantized MLP reference for the 8x8 MNIST demo.

PHASE-0 STUB. Built in Phase 1 on top of gemm_ref.quant_gemm, using the frozen arithmetic and
the committed quantized weights in model/mnist/. Defines the bit-exact expected classifications
that silicon must reproduce end-to-end.

Planned API (Phase 1):
    mlp_infer(image_u8_8x8, weights) -> (logits_i32, predicted_class)
"""

from __future__ import annotations


def mlp_infer(*args, **kwargs):  # pragma: no cover - Phase 1
    raise NotImplementedError(
        "mlp_ref.mlp_infer is a Phase-0 stub; implemented in Phase 1 on the frozen arithmetic."
    )


if __name__ == "__main__":
    print("model/mlp_ref.py: Phase-0 stub. 2-layer quantized MLP reference arrives in Phase 1.")
