#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "testdata"
VALID = OUT / "valid"
EXPLOITS = OUT / "exploits"

MAX_FRAME = 0x3FFFFFFE


def write(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{ln}\n" for ln in lines), newline="\n")


def main() -> None:
    write(VALID / "valid_001.frame", ["kind=query", "content=SELECT 1", "fill=0"])
    write(
        VALID / "valid_002.frame",
        ["kind=bind", "portal=", "stmt=stmt_orders", "params=8,16,32,64"],
    )
    write(
        VALID / "valid_003.frame",
        ["kind=copydata", "content=row,1,alice,active", "fill=0"],
    )
    write(
        VALID / "valid_004.frame",
        [
            "kind=parse",
            "stmt=s_lookup",
            "content=SELECT id FROM t WHERE k = $1",
            "fill=0",
        ],
    )
    write(VALID / "valid_005.frame", ["kind=execute", "portal=p_orders"])

    query_boundary_fill = MAX_FRAME - 4 - 1
    write(
        VALID / "valid_006.frame",
        ["kind=query", "content=", f"fill={query_boundary_fill}"],
    )
    copy_boundary_fill = MAX_FRAME - 4
    write(
        VALID / "valid_007.frame",
        ["kind=copydata", "content=", f"fill={copy_boundary_fill}"],
    )
    parse_boundary_fill = MAX_FRAME - 4 - 4
    write(
        VALID / "valid_008.frame",
        ["kind=parse", "stmt=", "content=", f"fill={parse_boundary_fill}"],
    )

    funcall_boundary_fill = MAX_FRAME - 8
    write(
        VALID / "valid_009.frame",
        ["kind=funcall", "content=", f"fill={funcall_boundary_fill}"],
    )
    batch_boundary_count = MAX_FRAME - 6
    write(
        VALID / "valid_010.frame",
        ["kind=batch", f"count={batch_boundary_count}", "elemsize=1"],
    )
    write(VALID / "valid_011.frame", ["kind=formats", "count=65535"])

    write(VALID / "valid_012.frame", ["kind=funcall", "content=arg0value"])
    write(VALID / "valid_013.frame", ["kind=batch", "count=4", "elemsize=8"])
    write(VALID / "valid_014.frame", ["kind=formats", "count=16"])

    write(
        EXPLOITS / "case_01.frame",
        ["kind=batch", "count=1000000", "elemsize=5000"],
    )
    write(
        EXPLOITS / "case_02.frame",
        ["kind=query", "content=", "fill=2147483650"],
    )
    write(
        EXPLOITS / "case_03.frame",
        ["kind=parse", "stmt=", "content=", "fill=2199999996"],
    )
    write(
        EXPLOITS / "case_04.frame",
        ["kind=copydata", "content=", "fill=1073741824"],
    )
    write(
        EXPLOITS / "case_05.frame",
        ["kind=formats", "count=100000"],
    )
    write(
        EXPLOITS / "case_06.frame",
        ["kind=parse", "stmt=", "content=", "fill=1499999996"],
    )
    write(
        EXPLOITS / "case_07.frame",
        ["kind=funcall", "content=", "fill=2147483650"],
    )
    write(
        EXPLOITS / "case_08.frame",
        [
            "kind=bind",
            "portal=",
            "stmt=stmt_bulk",
            "params=200000000,200000000,200000000,200000000,200000000,200000000",
        ],
    )


if __name__ == "__main__":
    main()
