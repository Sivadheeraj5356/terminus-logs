#!/usr/bin/env bash
# solve.sh — patches all bugs in the md_convert source and rebuilds.
set -euo pipefail

# ──────────────────────────────────────────────────────────────
# Fix A (parser.rs): Heading level off-by-one.
# The parser adds +1 to the hash count ("compensated indexing"),
# making # → level 2 instead of level 1. Fix: use hashes directly.
# ──────────────────────────────────────────────────────────────
python3 << 'PYEOF'
path = "/app/src/parser.rs"
with open(path) as f:
    src = f.read()

old = '                let level = (hashes + 1).min(6) as u8;'
assert old in src, f"Patch target not found: {old!r}"
src = src.replace(old, '                let level = hashes.min(6) as u8;', 1)

with open(path, "w") as f:
    f.write(src)
print("Fix A applied: heading level corrected (hashes+1 -> hashes)")
PYEOF

# ──────────────────────────────────────────────────────────────
# Fix B (parser.rs): Code fence closing doesn't match opening character.
# A ``` block is incorrectly closed by ~~~ and vice versa. Fix: only
# close when the fence character matches the opener.
# ──────────────────────────────────────────────────────────────
python3 << 'PYEOF'
path = "/app/src/parser.rs"
with open(path) as f:
    src = f.read()

old = '                if code_line.trim().starts_with("```") || code_line.trim().starts_with("~~~") {'
assert old in src, f"Patch target not found: {old!r}"
new = '                let fence_str: String = std::iter::repeat(fence_char).take(3).collect();\n                if code_line.trim().starts_with(&fence_str) {'
src = src.replace(old, new, 1)

with open(path, "w") as f:
    f.write(src)
print("Fix B applied: code fence closing now requires matching character")
PYEOF

# ──────────────────────────────────────────────────────────────
# Fix D (stats.rs): Integer division for average_blocks_per_file.
# The integer division truncates instead of using proper float division.
# ──────────────────────────────────────────────────────────────
python3 << 'PYEOF'
path = "/app/src/stats.rs"
with open(path) as f:
    src = f.read()

old = '        (total_blocks / total_files) as f64    // integer division truncation'
assert old in src, f"Patch target not found: {old!r}"
src = src.replace(old, '        (total_blocks as f64 / total_files as f64 * 10.0).round() / 10.0', 1)

with open(path, "w") as f:
    f.write(src)
print("Fix D applied: average_blocks_per_file now uses float division with rounding")
PYEOF

# ──────────────────────────────────────────────────────────────
# Fix E (stats.rs): Links in headings are silently discarded via
# a shadowed local variable. The outer link_count never accumulates
# heading link counts. Fix: replace the scoped let with actual accumulation.
# ──────────────────────────────────────────────────────────────
python3 << 'PYEOF'
path = "/app/src/stats.rs"
with open(path) as f:
    src = f.read()

old = '''                    // Accumulate link counts for heading text.
                    let link_count = count_links(text);  // scoped accumulator
                    let _ = link_count;  // merged in final tally below'''
new = '''                    link_count += count_links(text);'''
assert old in src, f"Patch target not found in stats.rs"
src = src.replace(old, new, 1)

with open(path, "w") as f:
    f.write(src)
print("Fix E applied: heading link counts now properly accumulate into link_count")
PYEOF


# ──────────────────────────────────────────────────────────────
# Rebuild and run
# ──────────────────────────────────────────────────────────────
cd /app
cargo build --release 2>&1
echo "Build successful"
/app/target/release/md_convert
echo "Converter ran — output written to /app/output/"
