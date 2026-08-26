"""Format detection and dataset I/O."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from cfaxis.error import FormatError
from cfaxis.formats.ccf import read_ccf, write_ccf
from cfaxis.formats.cft import read_cft, write_cft
from cfaxis.formats.common import Dataset


class FormatArg(str, Enum):
    AUTO = "auto"
    CCF = "ccf"
    CFT = "cft"


class FreqArg(str, Enum):
    MON = "mon"
    SEA = "sea"
    ANN = "ann"


def detect_format(path: Path) -> FormatArg:
    data = path.read_bytes()
    if len(data) >= 4 and data[:4] == b"CCF1":
        return FormatArg.CCF
    text = data.decode("utf-8", errors="replace")
    if text.startswith("#") or "time," in text:
        return FormatArg.CFT
    raise FormatError(f"cannot detect format for {path}")


def read_dataset(path: Path, from_fmt: FormatArg) -> Dataset:
    fmt = detect_format(path) if from_fmt == FormatArg.AUTO else from_fmt
    if fmt == FormatArg.CCF:
        return read_ccf(path)
    if fmt == FormatArg.CFT:
        return read_cft(path)
    raise FormatError(f"unsupported format {fmt}")


def write_dataset(path: Path, ds: Dataset, to_fmt: FormatArg) -> None:
    if to_fmt == FormatArg.AUTO:
        fmt = (
            FormatArg.CFT
            if path.suffix == ".cft"
            else FormatArg.CCF
        )
    else:
        fmt = to_fmt
    if fmt == FormatArg.CCF:
        write_ccf(path, ds)
    elif fmt == FormatArg.CFT:
        write_cft(path, ds)
    else:
        raise FormatError(f"unsupported format {fmt}")
