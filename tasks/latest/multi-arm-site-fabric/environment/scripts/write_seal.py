#!/usr/bin/env python3
"""Write the appliance seal digest under /usr/lib/sitefab."""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path("/usr/lib/sitefab")


def main() -> None:
    digest = hashlib.sha256(ROOT.joinpath("engine.py").read_bytes()).hexdigest()
    seal = ROOT.joinpath("SEAL")
    seal.write_text(digest + "\n", encoding="utf-8")
    seal.chmod(0o444)
    ROOT.joinpath("engine.py").chmod(0o555)
    ROOT.joinpath("law_digest.py").chmod(0o555)


if __name__ == "__main__":
    main()
