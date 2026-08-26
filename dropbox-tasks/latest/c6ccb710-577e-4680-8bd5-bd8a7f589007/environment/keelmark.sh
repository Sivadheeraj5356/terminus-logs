#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="${HARBOR_APP_ROOT:-/app}"
cd "$APP_ROOT"
mkdir -p "$APP_ROOT/bin" "$APP_ROOT/output"

# Keep cabal --offline from attempting Hackage HTTP when the runtime has no
# network (Harbor allow_internet=false). A local empty index is enough for the
# preinstalled system package database.
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

cabal build --offline exe:keelmark
BIN_PATH="$(cabal list-bin exe:keelmark)"
cp "$BIN_PATH" "$APP_ROOT/bin/keelmark"

exec "$APP_ROOT/bin/keelmark"
