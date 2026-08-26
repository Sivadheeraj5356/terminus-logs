#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="/app/build"
mkdir -p "$BUILD" /app/bin /app/output /app/output/stage /app/output/logs
cmake -S "$ROOT" -B "$BUILD"
cmake --build "$BUILD" -j2
install -m 0755 "$BUILD/sf_verify" /app/bin/sf_verify
install -m 0755 "$BUILD/sf_verify" "$ROOT/tools/sf_verify/sf_verify"
# Launcher at the public contract path: a script sitting beside the package root.
# Contract invokes `/app/environment/tools/sf_verify` — provide via PATH wrapper:
cat > /app/bin/sf_verify_public <<'EOF'
#!/usr/bin/env bash
exec /app/bin/sf_verify "$@"
EOF
chmod +x /app/bin/sf_verify_public
# Symlink public path through a non-directory name used by PATH:
# Create thin launcher that will be COPIED over — final public path resolution:
# Dockerfile adds a COPY of run_sf_verify.sh → /app/environment/tools/sf_verify.cmd
# Instruction will call: `/app/environment/tools/sf_verify/sf_verify`
true
