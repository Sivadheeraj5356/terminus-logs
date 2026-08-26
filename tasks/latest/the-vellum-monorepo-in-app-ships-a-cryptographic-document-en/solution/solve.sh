#!/usr/bin/env bash
# Reference solution for offline-release-provenance-quorum.
#
# Fixes the release pipeline under /app so that `/app/bin/release` produces a
# byte-for-byte reproducible qualification bundle across source roots, all three
# surfaces (native library, Python wheel, Node package) report one identity and
# agree on documented operations, the dependency inventory matches the closure
# actually compiled, and the provenance binds the final shipped bytes.
set -euo pipefail

APP="${1:-/app}"
cd "$APP"

# --- Fix 1: identity capabilities come from compiled features, not a declared
#            environment list. The library must report what it actually can do.
python3 - "$APP/crates/bridge/build.rs" <<'PY'
import sys, io
p = sys.argv[1]
s = open(p).read()
s = s.replace("let mut caps = declared_capabilities();",
              "let mut caps = compiled_capabilities();")
open(p, "w").write(s)
PY

# --- Fix 2: developer capability overrides must never alter release output.
python3 - "$APP/support/src/plan.rs" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
s = s.replace("    apply_local_overrides(&mut capabilities);\n", "")
open(p, "w").write(s)
PY

# --- Fix 3: the dependency inventory must describe the closure actually
#            compiled. Optional, disabled dependencies are not part of it.
python3 - "$APP/tools/inventory/src/main.rs" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
needle = "        if !in_deps || trimmed.is_empty() || trimmed.starts_with('#') {\n            continue;\n        }\n"
repl = ("        if !in_deps || trimmed.is_empty() || trimmed.starts_with('#') {\n"
        "            continue;\n        }\n"
        "        if trimmed.contains(\"optional = true\") || trimmed.contains(\"optional=true\") {\n"
        "            continue;\n        }\n")
assert needle in s, "inventory dep-filter anchor not found"
s = s.replace(needle, repl)
open(p, "w").write(s)
PY

# --- Fix 4: the Python wheel ships the authoritative native library (built once
#            with the release formatter) and is a deterministic archive.
cat > "$APP/python/build_backend.py" <<'PY'
#!/usr/bin/env python3
"""Assemble the Vellum wheel.

Invoked by the release orchestrator with the resolved plan. Produces
vellum-<version>-py3-none-linux_x86_64.whl under the output directory. The wheel
bundles the authoritative native library supplied by the orchestrator and is a
deterministic archive (sorted entries, fixed timestamps, normalized modes).
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import shutil
import sys
import zipfile
from pathlib import Path


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--native", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--epoch", type=int, required=True)
    ap.add_argument("--features", default="")
    return ap.parse_args()


def sha256_b64(data: bytes) -> str:
    digest = hashlib.sha256(data).digest()
    return "sha256=" + base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def main() -> int:
    args = parse_args()
    source_root = Path(args.source_root)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Ship the authoritative native library produced by the orchestrator.
    native = Path(args.native)

    stage = out_dir / "_wheel_stage"
    if stage.exists():
        shutil.rmtree(stage)
    pkg = stage / "vellum"
    pkg.mkdir(parents=True)

    src_pkg = source_root / "python" / "src" / "vellum"
    for name in ["__init__.py", "api.py", "_loader.py"]:
        shutil.copy2(src_pkg / name, pkg / name)
    shutil.copy2(native, pkg / "libvellum.so")

    dist_info = stage / f"vellum-{args.version}.dist-info"
    dist_info.mkdir()
    (dist_info / "WHEEL").write_text(
        "Wheel-Version: 1.0\n"
        "Generator: vellum-backend\n"
        "Root-Is-Purelib: false\n"
        "Tag: py3-none-linux_x86_64\n"
    )
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.1\n"
        "Name: vellum\n"
        f"Version: {args.version}\n"
        "Summary: Vellum document engine\n"
    )

    files = sorted(
        (p for p in stage.rglob("*") if p.is_file()),
        key=lambda p: p.relative_to(stage).as_posix(),
    )

    record_lines = []
    for path in files:
        rel = path.relative_to(stage).as_posix()
        data = path.read_bytes()
        record_lines.append(f"{rel},{sha256_b64(data)},{len(data)}")
    record_path = dist_info / "RECORD"
    record_lines.append(f"vellum-{args.version}.dist-info/RECORD,,")
    record_path.write_text("\n".join(record_lines) + "\n")
    files.append(record_path)

    wheel_name = f"vellum-{args.version}-py3-none-linux_x86_64.whl"
    wheel_path = out_dir / wheel_name
    if wheel_path.exists():
        wheel_path.unlink()

    date_time = (1980, 1, 1, 0, 0, 0)
    entries = sorted(files, key=lambda p: p.relative_to(stage).as_posix())
    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in entries:
            rel = path.relative_to(stage).as_posix()
            info = zipfile.ZipInfo(rel, date_time=date_time)
            info.external_attr = (0o644 & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, path.read_bytes())

    shutil.rmtree(stage)
    print(str(wheel_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
PY

# --- Fix 5: the Node CLI is built with the release feature set (so documented
#            operations work) and ships the freshly generated declarations.
cat > "$APP/node/scripts/build.sh" <<'SH'
#!/usr/bin/env bash
# Stage the Node package contents: sources, declarations, and the native CLI.
# Usage: build.sh <source-root> <stage-dir> <generated-dir> <features>
set -euo pipefail

SRC="$1"
STAGE="$2"
GENERATED="$3"
FEATURES="${4:-}"

mkdir -p "$STAGE/bin" "$STAGE/decl"
cp "$SRC/node/src/index.js" "$STAGE/index.js"
cp "$SRC/node/package.json" "$STAGE/package.json"
cp "$GENERATED/node_decl.txt" "$STAGE/decl/node_decl.txt"

FEATFLAG=""
if [ -n "$FEATURES" ]; then
    FEATFLAG="--features ${FEATURES// /,}"
fi

export CARGO_TARGET_DIR="$SRC/node/native-target"
# shellcheck disable=SC2086
cargo build --release --manifest-path "$SRC/Cargo.toml" -p vellum-cli \
    --no-default-features $FEATFLAG
cp "$SRC/node/native-target/release/vellum-cli" "$STAGE/bin/vellum-cli"
strip --strip-unneeded "$STAGE/bin/vellum-cli" 2>/dev/null || true
chmod 0755 "$STAGE/bin/vellum-cli"
SH

# --- Fix 6: the Node tarball is a deterministic archive.
cat > "$APP/node/scripts/pack.sh" <<'SH'
#!/usr/bin/env bash
# Produce the npm tarball from a staged package directory.
# Usage: pack.sh <stage-parent> <output-tgz> <epoch>
set -euo pipefail

STAGE_PARENT="$1"
OUT="$2"
EPOCH="$3"

cd "$STAGE_PARENT"
tar --sort=name \
    --mtime="@$EPOCH" \
    --owner=0 --group=0 --numeric-owner \
    --format=gnu \
    -cf - package \
  | gzip -n -6 > "$OUT"
SH

# --- Fix 7: the orchestrator: reproducible native build, always-fresh interface
#            generation, and provenance that binds the final shipped bytes.
cat > "$APP/scripts/release" <<'SH'
#!/usr/bin/env bash
# Vellum release orchestrator. Produces a qualification bundle from a source
# root. See docs/release-contract.md for the public contract.
set -euo pipefail

export CARGO_HOME="${CARGO_HOME:-/usr/local/cargo}"
export RUSTUP_HOME="${RUSTUP_HOME:-/usr/local/rustup}"
export PATH="$CARGO_HOME/bin:$PATH"

SELF="$(cd "$(dirname "$0")" && pwd)"
DEFAULT_ROOT="$(cd "$SELF/.." && pwd)"

SOURCE_ROOT="$DEFAULT_ROOT"
OUTPUT="/output/release"
while [ "$#" -gt 0 ]; do
    case "$1" in
        --source-root) SOURCE_ROOT="$2"; shift 2 ;;
        --output) OUTPUT="$2"; shift 2 ;;
        *) echo "release: unknown argument $1" >&2; exit 2 ;;
    esac
done

SOURCE_ROOT="$(cd "$SOURCE_ROOT" && pwd)"
mkdir -p "$OUTPUT"
OUTPUT="$(cd "$OUTPUT" && pwd)"
cd "$SOURCE_ROOT"

rm -rf "$OUTPUT"
mkdir -p "$OUTPUT/native" "$OUTPUT/python" "$OUTPUT/node" "$OUTPUT/metadata"

export CARGO_HOME="${CARGO_HOME:-/usr/local/cargo}"
export RUSTUP_HOME="${RUSTUP_HOME:-/usr/local/rustup}"

# --- Build release tooling ------------------------------------------------
cargo build --release -p planctl -p idlgen -p inventory-tool -p attest >/dev/null
TOOLS="$SOURCE_ROOT/target/release"

# --- Resolve the plan (config is authoritative; dev overrides are ignored) --
PLAN_JSON="$("$TOOLS/planctl" resolve --root "$SOURCE_ROOT")"
VERSION="$(printf '%s' "$PLAN_JSON" | jq -r .version)"
REVISION="$(printf '%s' "$PLAN_JSON" | jq -r .revision)"
EPOCH="$(printf '%s' "$PLAN_JSON" | jq -r .epoch)"
FEATURES="$("$TOOLS/planctl" features --root "$SOURCE_ROOT")"
export SOURCE_DATE_EPOCH="$EPOCH"

# --- Interface generation (pure function of the IDL; always regenerated) ----
GEN="$SOURCE_ROOT/target/gen"
rm -rf "$GEN"; mkdir -p "$GEN"
"$TOOLS/idlgen" --idl "$SOURCE_ROOT/interface/document.idl" --out-dir "$GEN" >/dev/null
ABI="$(sha256sum "$GEN/abi.json" | awk '{print $1}')"

# --- Dependency inventory (closure actually compiled) ---------------------
"$TOOLS/inventory" --root "$SOURCE_ROOT" > "$OUTPUT/metadata/dependency-inventory.json"
CLOSURE="$(jq -r .closure_digest "$OUTPUT/metadata/dependency-inventory.json")"

# --- Native library + CLI (reproducible: no absolute paths, no build-id) ---
export VELLUM_VERSION="$VERSION"
export VELLUM_REVISION="$REVISION"
export VELLUM_ABI_FINGERPRINT="$ABI"
export VELLUM_DEP_CLOSURE="$CLOSURE"

FEATFLAG=""
if [ -n "$FEATURES" ]; then
    FEATFLAG="--features ${FEATURES// /,}"
fi

export RUSTFLAGS="-C debuginfo=0 -C strip=symbols --remap-path-prefix=$SOURCE_ROOT=/vellum --remap-path-prefix=$CARGO_HOME=/cargo --remap-path-prefix=$RUSTUP_HOME=/rustup"
# shellcheck disable=SC2086
cargo build --release -p bridge -p vellum-cli --no-default-features $FEATFLAG >/dev/null

# Normalize the native library to its final shipped form BEFORE it is measured.
cp "$SOURCE_ROOT/target/release/libvellum.so" "$OUTPUT/native/libvellum.so"
strip --strip-unneeded "$OUTPUT/native/libvellum.so" 2>/dev/null || true
objcopy --remove-section .note.gnu.build-id "$OUTPUT/native/libvellum.so" 2>/dev/null || true
chmod 0644 "$OUTPUT/native/libvellum.so"

"$SOURCE_ROOT/target/release/vellum-cli" identity > "$SOURCE_ROOT/target/identity.json"

# --- Python wheel (ships the authoritative native library) ----------------
python3 "$SOURCE_ROOT/python/build_backend.py" \
    --source-root "$SOURCE_ROOT" \
    --out "$OUTPUT/python" \
    --native "$OUTPUT/native/libvellum.so" \
    --version "$VERSION" \
    --epoch "$EPOCH" \
    --features "$FEATURES" >/dev/null

# --- Node package ---------------------------------------------------------
NODE_STAGE="$SOURCE_ROOT/target/node-stage"
rm -rf "$NODE_STAGE"; mkdir -p "$NODE_STAGE/package"
bash "$SOURCE_ROOT/node/scripts/build.sh" "$SOURCE_ROOT" "$NODE_STAGE/package" "$GEN" "$FEATURES"
bash "$SOURCE_ROOT/node/scripts/pack.sh" "$NODE_STAGE" "$OUTPUT/node/vellum-node-$VERSION.tgz" "$EPOCH"

# --- Provenance binds the FINAL shipped bytes -----------------------------
WHEEL="$(ls "$OUTPUT/python"/*.whl | head -n1)"
TGZ="$OUTPUT/node/vellum-node-$VERSION.tgz"

"$TOOLS/attest" \
    --identity "$SOURCE_ROOT/target/identity.json" \
    --output-root "$OUTPUT" \
    --subject "native/libvellum.so" \
    --subject "python/$(basename "$WHEEL")" \
    --subject "node/$(basename "$TGZ")" \
    --subject "metadata/dependency-inventory.json" \
    --out "$OUTPUT/metadata/provenance.json"

openssl pkeyutl -sign \
    -inkey "$SOURCE_ROOT/policy/qualification-ed25519.key" \
    -rawin -in "$OUTPUT/metadata/provenance.json" \
    -out "$OUTPUT/metadata/provenance.sig"
cp "$SOURCE_ROOT/policy/qualification-ed25519.pub" "$OUTPUT/metadata/release-public.pem"

# --- SHA256SUMS -----------------------------------------------------------
( cd "$OUTPUT"
  find . -type f ! -name SHA256SUMS -print0 \
    | sort -z \
    | while IFS= read -r -d '' f; do
        rel="${f#./}"
        printf '%s  %s\n' "$(sha256sum "$f" | awk '{print $1}')" "$rel"
      done > SHA256SUMS )

echo "release complete: $OUTPUT"
SH
chmod +x "$APP/scripts/release" "$APP/node/scripts/build.sh" "$APP/node/scripts/pack.sh"

echo "solve.sh: patches applied"
