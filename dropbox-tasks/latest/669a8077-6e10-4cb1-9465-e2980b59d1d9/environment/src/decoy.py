"""Aggregate gate counters for inventory-style dashboards."""


def quick_gate_count(passed: int, failed: int) -> int:
    return passed + failed
