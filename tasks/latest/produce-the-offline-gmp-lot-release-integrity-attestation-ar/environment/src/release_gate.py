"""GMP lot-release integrity attestation security review entrypoint."""

from __future__ import annotations

import sys

from attestation.commands import run


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        code = run(args)
    except Exception as exc:  # noqa: BLE001 — usage errors become exit 2
        sys.stderr.write(f"usage error: {exc}\n")
        raise SystemExit(2) from exc
    raise SystemExit(code)


if __name__ == "__main__":
    main()
