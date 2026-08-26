from __future__ import annotations

from .io_util import read_json


def load_graph(path: str) -> dict[str, object]:
    return read_json(__import__("pathlib").Path(path))


def load_consumer(path: str) -> dict[str, object]:
    return read_json(__import__("pathlib").Path(path))
