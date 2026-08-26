"""Format checker for the practice batch.

This runs your solver over `practice_challenges.txt` and checks only that its
output is well formed: one line per challenge, the same ids, exactly `2*L`
lowercase hex characters, and the required header on the recovered bytes.

It does NOT check correctness. No answers ship with the practice batch and no
ground truth exists on this host, so a clean run here says nothing at all about
whether a recovery is right. Usage:

    python3 local_check.py julia /app/environment/attack/main.jl
"""

import os
import re
import subprocess
import sys

HEADER = "cafe"
HEX = re.compile(r"\A[0-9a-f]+\Z")


def _challenges(path):
    with open(path) as f:
        lines = [ln for ln in (x.strip() for x in f) if ln]
    out = []
    for line in lines[1:]:
        tok = line.split()
        out.append({"id": tok[0], "L": int(tok[2])})
    return out


def main():
    if len(sys.argv) < 3:
        print("usage: python3 local_check.py julia <main.jl>")
        return 1
    here = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(here, "practice_challenges.txt")
    chs = _challenges(src)
    out_path = os.path.join(here, "_practice_out.txt")
    proc = subprocess.run([sys.argv[1], sys.argv[2], src, out_path])
    if proc.returncode != 0:
        print("solver exited non-zero")
        return 1
    seen = {}
    with open(out_path) as f:
        for line in f:
            p = line.split()
            if len(p) >= 2:
                seen[p[0]] = p[1]
    os.remove(out_path)

    bad = 0
    for c in chs:
        h = seen.get(c["id"])
        if h is None:
            why = "no line emitted"
        elif len(h) != 2 * c["L"] or not HEX.match(h):
            why = f"expected {2 * c['L']} lowercase hex characters, got {len(h)}"
        elif not h.startswith(HEADER):
            why = f"recovered bytes do not start with the {HEADER} header"
        else:
            continue
        bad += 1
        print(f"challenge {c['id']}: MALFORMED ({why})")

    extra = sorted(set(seen) - {c["id"] for c in chs})
    for e in extra:
        bad += 1
        print(f"unexpected id in output: {e}")

    print(f"{len(chs) - bad}/{len(chs)} well formed")
    print("well-formedness only: this check cannot tell you if a recovery is right")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
