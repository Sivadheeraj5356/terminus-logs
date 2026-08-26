"""Conching window midpoint helpers for beta-six lattice chronicle."""
from __future__ import annotations


def polymorph_midpoint(min_c: float, max_c: float) -> float:
    return (min_c + max_c) / 2.0


def window_table_paths() -> tuple[str, str]:
  return (
      "/app/conching-network/conching-window-table.json",
      "/app/lattice-invariant-catalog/formulation-catalog.json",
  )
