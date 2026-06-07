"""Shared helpers for TensorTile cocotb benches (pack/unpack flattened buses, signed reads)."""
from __future__ import annotations


def pack(vals, w: int) -> int:
    """Pack a list of ints (LSB-first, element 0 in the low bits) into one integer."""
    mask = (1 << w) - 1
    out = 0
    for i, v in enumerate(vals):
        out |= (int(v) & mask) << (i * w)
    return out


def unpack_signed(word: int, n: int, w: int):
    """Unpack n signed w-bit fields (element 0 in the low bits)."""
    res = []
    for i in range(n):
        v = (word >> (i * w)) & ((1 << w) - 1)
        if v >= (1 << (w - 1)):
            v -= (1 << w)
        res.append(v)
    return res


def rd_int(sig) -> int:
    """Read a cocotb handle value as a (possibly X-containing) int; X/Z -> raises ValueError."""
    return int(sig.value)
