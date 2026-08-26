#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${HARBOR_APP_ROOT:-/app}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_ROOT"

# Seed a local Hackage index so cabal --offline never attempts HTTP under
# allow_internet=false (mirrors lookup otherwise aborts the build).
CABAL_HOME="${CABAL_DIR:-/var/cache/cabal}"
mkdir -p "$CABAL_HOME/packages/hackage.haskell.org"
if [[ ! -f "$CABAL_HOME/packages/hackage.haskell.org/00-index.tar" ]]; then
  tar -cf "$CABAL_HOME/packages/hackage.haskell.org/00-index.tar" -T /dev/null
fi
if [[ ! -f "$CABAL_HOME/config" ]]; then
  cat > "$CABAL_HOME/config" <<'EOF'
repository hackage.haskell.org
  url: http://hackage.haskell.org/
  secure: False

remote-repo-cache: /var/cache/cabal/packages
world-file: /var/cache/cabal/world
extra-prog-path: /var/cache/cabal/bin
store-dir: /var/cache/cabal/store
jobs: $ncpus
EOF
fi

# Drop host-local overrides that undefine the gate-v2 stream profile.
rm -f "$APP_ROOT/cabal.project.local"

# Restore the workspace-level package set (drop the unsatisfiable text pin).
cat > "$APP_ROOT/cabal.project" <<'EOF'
packages: packages/keelmark-core
          packages/keelmark-report
          packages/keelmark-app
EOF

# keelmark-core: break the dependency cycle, pin aeson to the installed 2.0
# line, restore containers, expose every shipped module, drop compat, align
# edition package version, and compile the gate-v2 stream profile.
cat > "$APP_ROOT/packages/keelmark-core/keelmark-core.cabal" <<'EOF'
cabal-version:      2.4
name:               keelmark-core
version:            1.4.2
synopsis:           Keelmark core telemetry parsing and calibration
license:            MIT
build-type:         Simple

library
  hs-source-dirs:   src
  exposed-modules:  Keelmark.Types
                    Keelmark.Scan
                    Keelmark.Classify
  cpp-options:      -DKEELMARK_GATE_V2
  build-depends:    base >= 4.14 && < 5
                  , aeson >= 2.0 && < 2.1
                  , bytestring
                  , text
                  , containers
  default-language: Haskell2010
EOF

# keelmark-report: depends on keelmark-core, src only, same gate-v2 profile.
cat > "$APP_ROOT/packages/keelmark-report/keelmark-report.cabal" <<'EOF'
cabal-version:      2.4
name:               keelmark-report
version:            1.4.2
synopsis:           Keelmark packaging report emission
license:            MIT
build-type:         Simple

library
  hs-source-dirs:   src
  exposed-modules:  Keelmark.Emit
  cpp-options:      -DKEELMARK_GATE_V2
  build-depends:    base >= 4.14 && < 5
                  , keelmark-core
                  , bytestring
                  , filepath
  default-language: Haskell2010
EOF

# keelmark executable: build-type Simple (no custom Setup shipped).
cat > "$APP_ROOT/packages/keelmark-app/keelmark.cabal" <<'EOF'
cabal-version:      2.4
name:               keelmark
version:            1.4.2
synopsis:           Keelmark drydock keel-block load packaging console
license:            MIT
build-type:         Simple

executable keelmark
  main-is:          Main.hs
  hs-source-dirs:   app
  build-depends:    base >= 4.14 && < 5
                  , keelmark-core
                  , keelmark-report
                  , aeson
                  , bytestring
                  , text
                  , containers
                  , directory
                  , filepath
  default-language: Haskell2010
EOF

# Restore the maintained Scan, Classify, and Emit modules the migration never landed.
mkdir -p "$APP_ROOT/packages/keelmark-core/src/Keelmark"
mkdir -p "$APP_ROOT/packages/keelmark-report/src/Keelmark"
cp "$SCRIPT_DIR/restore/Scan.hs" \
  "$APP_ROOT/packages/keelmark-core/src/Keelmark/Scan.hs"
cp "$SCRIPT_DIR/restore/Classify.hs" \
  "$APP_ROOT/packages/keelmark-core/src/Keelmark/Classify.hs"
cp "$SCRIPT_DIR/restore/Emit.hs" \
  "$APP_ROOT/packages/keelmark-report/src/Keelmark/Emit.hs"

# Align the edition ABI pin with the contract so no abi_miss deferrals ship.
python3 - <<'PY'
import json, os
from pathlib import Path
root = Path(os.environ.get("HARBOR_APP_ROOT", "/app"))
path = root / "keelmark-policy" / "edition-policy.json"
data = json.loads(path.read_text(encoding="utf-8"))
data["edition_abi"] = "9.0-cabal-3.4"
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY

bash "$APP_ROOT/keelmark.sh"

for f in pack_inventory.json tension_alerts.json deferred.json summary.json gate_seal.txt; do
  if [[ ! -s "$APP_ROOT/output/$f" ]]; then
    echo "Oracle missing output: $APP_ROOT/output/$f" >&2
    exit 1
  fi
done

echo "Oracle solution completed."
