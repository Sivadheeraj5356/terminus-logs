"""Collect exported symbol sets for linked binaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from probes.nm_parse import nm_defined_symbols, readobj_exports


def linked_symbol_set(binary: Path) -> list[str]:
    nm_syms = nm_defined_symbols(binary)
    if nm_syms:
        return nm_syms
    return readobj_exports(binary)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("binary")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    symbols = linked_symbol_set(Path(args.binary))
    if args.out:
        Path(args.out).write_text(json.dumps(symbols, indent=2) + "\n", encoding="utf-8")
    else:
        print(json.dumps(symbols))


if __name__ == "__main__":
    main()
