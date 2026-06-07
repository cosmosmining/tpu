"""
gemm_ref.py — bit-exact quantized GEMM reference (THE arithmetic contract).

PHASE-0 STUB. The real implementation is written in Phase 1, *after* docs/SPEC.md §2
(accumulation width/signedness, per-stage saturation bounds, the exact requant rounding rule)
is frozen and operator-approved. This model then defines the arithmetic for RTL and silicon:
silicon == RTL == model, to the bit. It may NEVER be edited to make failing RTL pass — changes
require a SPEC.md citation and a DECISIONS.md entry.

Planned API (Phase 1):
    quant_gemm(weights_i8, acts_i8, *, acc_w=24, bias_i16=None, requant_shift, relu=False,
               array_n=4) -> np.ndarray[int8]
    plus directed unit tests covering most-negative operands, saturation, and rounding ties.
"""

from __future__ import annotations


def quant_gemm(*args, **kwargs):  # pragma: no cover - Phase 1
    raise NotImplementedError(
        "gemm_ref.quant_gemm is a Phase-0 stub; implemented in Phase 1 after SPEC §2 is frozen."
    )


if __name__ == "__main__":
    print("model/gemm_ref.py: Phase-0 stub. Bit-exact GEMM reference arrives in Phase 1.")
