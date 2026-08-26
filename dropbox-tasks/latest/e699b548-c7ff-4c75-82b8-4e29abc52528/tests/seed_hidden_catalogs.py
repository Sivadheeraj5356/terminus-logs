"""Materialize verifier-only CLFC catalogs at test runtime (not in the agent image)."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    tests_dir = Path(__file__).resolve().parent
    if str(tests_dir) not in sys.path:
        sys.path.insert(0, str(tests_dir))
    from fixtures.fixture_data import HIDDEN_CATALOGS, write_clfc

    dest = Path("/opt/verifier-fixtures/catalogs")
    dest.mkdir(parents=True, exist_ok=True)
    for name, frags in sorted(HIDDEN_CATALOGS.items()):
        write_clfc(dest / f"{name}.clfc", frags)


if __name__ == "__main__":
    main()
