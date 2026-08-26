"""Map translation units to logical LTO module names."""

from __future__ import annotations

MODULE_SOURCES = {
    "anchor": ["anchor.cpp"],
    "dispatch": ["dispatch.cpp"],
    "consumer": ["consumer.cpp"],
    "gate_abi": ["gate_abi.cpp"],
    "main": ["main.cpp"],
}

GEN_SENSITIVE = {"dispatch", "consumer", "gate_abi", "main"}


def all_modules() -> list[str]:
    return list(MODULE_SOURCES.keys())


def source_name(module: str) -> str:
  return MODULE_SOURCES[module][0]
