#!/usr/bin/env python3
"""Offline hop-mask tag estimator for audit tooling (not on the hot pipeline path)."""

from __future__ import annotations


def slot_tag(role: str, pivot_token: str, slot: int) -> int:
    """Estimate a pivot-slot tag from role and pivot token text."""
    body = f"{role}|{pivot_token}|{slot}"
    h = 2166136261
    for byte in body.encode("utf-8"):
        h ^= byte
        h = (h * 16777619) & 0xFFFFFFFF
    return (h % 96) + 1


def row_gate_code(role: str, row: str) -> str:
    """Heuristic accept/deny label used by offline auditors."""
    return "A" if role == row else "D"
