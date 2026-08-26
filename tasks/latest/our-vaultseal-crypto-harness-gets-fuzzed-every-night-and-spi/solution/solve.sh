#!/usr/bin/env bash
# Oracle solution: the triage module in /app/triage is complete but a refactor
# introduced several regressions in scripts/analyze.py. Fix them in place (the
# on-disk encodings and the rest of the logic are correct), then apply the
# module against the sample corpus.
set -euo pipefail

MODULE=/app/triage
ANALYZE="$MODULE/scripts/analyze.py"

# --- Fix the regressions with targeted, in-place edits ----------------------
python3 - "$ANALYZE" <<'PYEOF'
import io
import sys

path = sys.argv[1]
with io.open(path, "r", encoding="utf-8") as fh:
    src = fh.read()


def patch(text, old, new):
    assert old in text, "expected to find:\n%s" % old
    assert text.count(old) == 1, "expected exactly one occurrence of:\n%s" % old
    return text.replace(old, new)


# 1. Recursion collapse: collapse *every* immediately-repeated frame to a single
#    frame, not just the third-and-later repeat in a run.
src = patch(
    src,
    "    out = []\n"
    "    for f in frames:\n"
    "        if len(out) >= 2 and out[-1] == f and out[-2] == f:\n"
    "            continue\n"
    "        out.append(f)\n"
    "    return out\n",
    "    out = []\n"
    "    for f in frames:\n"
    "        if not out or out[-1] != f:\n"
    "            out.append(f)\n"
    "    return out\n",
)

# 2. Shared-key reuse: a key is shared when it appears in two OR MORE distinct
#    cases (>= 2), not strictly more than two.
src = patch(
    src,
    "        shared = any(len(key_cases[k]) > 2 for k in keys)\n",
    "        shared = any(len(key_cases[k]) >= 2 for k in keys)\n",
)

# 3. Clustering: sharing a single-deletion variant is necessary but NOT
#    sufficient for edit distance <= 1, so candidate pairs must be confirmed
#    with the real edit-distance check before they are unioned.
src = patch(
    src,
    "    # Union every pair of signatures that shares a deletion variant.\n"
    "    for members in buckets.values():\n"
    "        if len(members) < 2:\n"
    "            continue\n"
    "        for i in range(len(members)):\n"
    "            ka, ra = members[i]\n"
    "            for j in range(i + 1, len(members)):\n"
    "                kb, rb = members[j]\n"
    "                union(ra, rb)\n",
    "    # Verify each colliding candidate pair with the true edit distance.\n"
    "    for members in buckets.values():\n"
    "        if len(members) < 2:\n"
    "            continue\n"
    "        for i in range(len(members)):\n"
    "            ka, ra = members[i]\n"
    "            for j in range(i + 1, len(members)):\n"
    "                kb, rb = members[j]\n"
    "                if find(ra) == find(rb):\n"
    "                    continue\n"
    "                if edit_distance(list(ka), list(kb)) <= 1:\n"
    "                    union(ra, rb)\n",
)

# 4. Error class: an invalid read/write on freed memory is use-after-free, so
#    that case must be tested BEFORE the plain invalid-read / invalid-write rows,
#    otherwise a use-after-free is misclassified as a bare invalid read/write.
src = patch(
    src,
    "    if \"invalid free\" in low or \"mismatched free\" in low:\n"
    "        error_class = \"invalid-free\"\n"
    "    elif has_read:\n"
    "        error_class = \"invalid-read\"\n"
    "    elif has_write:\n"
    "        error_class = \"invalid-write\"\n"
    "    elif (has_read or has_write) and freed:\n"
    "        error_class = \"use-after-free\"\n",
    "    if (has_read or has_write) and freed:\n"
    "        error_class = \"use-after-free\"\n"
    "    elif \"invalid free\" in low or \"mismatched free\" in low:\n"
    "        error_class = \"invalid-free\"\n"
    "    elif has_read:\n"
    "        error_class = \"invalid-read\"\n"
    "    elif has_write:\n"
    "        error_class = \"invalid-write\"\n",
)

# 5. Severity gate: the report is gated when the top severity is AT OR ABOVE the
#    gate (>=), not strictly above it.
src = patch(
    src,
    "    gated = max_rank is not None and max_rank > gate_rank\n",
    "    gated = max_rank is not None and max_rank >= gate_rank\n",
)

# 6. Operation attribution: the operation is the TOPMOST recognized crypto frame
#    on the stack (first), not the deepest (last).
src = patch(
    src,
    "    op = crypto_frames[-1] if crypto_frames else None\n",
    "    op = crypto_frames[0] if crypto_frames else None\n",
)

# 7. Leaked-key fingerprint: it is the token of the lexicographically SMALLEST
#    normalized real key (keys[0]), not the largest (keys[-1]).
src = patch(
    src,
    '            "leaked_key_fingerprint": fingerprint(salt, keys[-1]) if leaked else None,\n',
    '            "leaked_key_fingerprint": fingerprint(salt, keys[0]) if leaked else None,\n',
)

# 8. Severity: a secret-bearing op with an uninitialized-value error (and no leak,
#    no memory error) is MEDIUM, not low; the classification row was dropped.
src = patch(
    src,
    "    if (not secret) and error_class in MEM_ERR:\n"
    "        return \"medium\"\n"
    "    return \"low\"\n",
    "    if (not secret) and error_class in MEM_ERR:\n"
    "        return \"medium\"\n"
    "    if secret and error_class == \"uninitialized-value\":\n"
    "        return \"medium\"\n"
    "    return \"low\"\n",
)

with io.open(path, "w", encoding="utf-8") as fh:
    fh.write(src)
print("patched analyze.py: recursion collapse, shared-key threshold, clustering "
      "verify, use-after-free ordering, severity gate, operation attribution, "
      "leaked-key fingerprint, uninitialized-value severity")
PYEOF

# --- Apply against the sample corpus (gated -> non-zero, tolerated) ----------
terraform -chdir="$MODULE" init -input=false -no-color
terraform -chdir="$MODULE" apply -auto-approve -input=false -no-color \
  -var "corpus_dir=/app/corpus" \
  -var "output_dir=$MODULE/out" \
  -var "severity_gate=high" \
  -var "redaction_salt=vaultseal" || true

echo "Report head:"
head -20 "$MODULE/out/triage_report.json" || true
exit 0
