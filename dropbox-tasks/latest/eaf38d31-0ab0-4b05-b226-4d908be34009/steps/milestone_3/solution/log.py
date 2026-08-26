"""Append-only, hash-chained transparency log.

Each entry commits to the previous entry's hash, forming a tamper-evident
chain. The genesis previous-hash is 64 zero hex characters.
"""

import hashlib
import json
import threading
from pathlib import Path

GENESIS_PREV = "0" * 64


def _entry_hash(index: int, prev_hash: str, manifest_hash: str, signature: str) -> str:
    payload = json.dumps(
        {
            "index": index,
            "prev_hash": prev_hash,
            "manifest_hash": manifest_hash,
            "signature": signature,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class TransparencyLog:
    def __init__(self, path: str | None = None):
        self._lock = threading.Lock()
        self._entries: list[dict] = []
        self._seen: set[tuple[str, str]] = set()
        self._path = Path(path) if path else None
        if self._path and self._path.exists():
            for line in self._path.read_text().splitlines():
                if line.strip():
                    e = json.loads(line)
                    self._entries.append(e)
                    self._seen.add((e["manifest_hash"], e["signature"]))

    def append(self, manifest_hash: str, signature: str) -> dict:
        """Append a new entry. Raises KeyError on replay of (manifest_hash, signature)."""
        with self._lock:
            if (manifest_hash, signature) in self._seen:
                raise KeyError("replayed entry: (manifest_hash, signature) already logged")
            index = len(self._entries)
            prev_hash = self._entries[-1]["entry_hash"] if self._entries else GENESIS_PREV
            entry_hash = _entry_hash(index, prev_hash, manifest_hash, signature)
            entry = {
                "index": index,
                "prev_hash": prev_hash,
                "manifest_hash": manifest_hash,
                "signature": signature,
                "entry_hash": entry_hash,
            }
            self._entries.append(entry)
            self._seen.add((manifest_hash, signature))
            if self._path:
                with open(self._path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, sort_keys=True) + "\n")
            return entry

    def entries(self) -> list[dict]:
        with self._lock:
            return list(self._entries)

    def verify_chain(self) -> bool:
        with self._lock:
            prev = GENESIS_PREV
            for i, e in enumerate(self._entries):
                if e["index"] != i or e["prev_hash"] != prev:
                    return False
                expect = _entry_hash(i, prev, e["manifest_hash"], e["signature"])
                if expect != e["entry_hash"]:
                    return False
                prev = e["entry_hash"]
            return True
