from __future__ import annotations


def confidence_label(trades: int, incomplete: bool) -> str:
    if incomplete or trades < 30:
        return "LOW"
    if trades < 100:
        return "MEDIUM"
    return "HIGH"
