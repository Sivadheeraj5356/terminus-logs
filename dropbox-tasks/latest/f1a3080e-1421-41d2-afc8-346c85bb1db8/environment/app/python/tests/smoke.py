"""Developer smoke check for the Python source package (run by dev-check)."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    import vellum

    ident = vellum.identity()
    for key in ["version", "revision", "capabilities", "release_id"]:
        assert key in ident, f"missing identity field {key}"

    basic = json.loads((ROOT.parent / "fixtures" / "documents" / "basic.json").read_text())
    digest = vellum.canonical_digest(basic)
    assert len(digest) == 64, "digest should be 64 hex chars"
    print("python smoke ok:", digest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
