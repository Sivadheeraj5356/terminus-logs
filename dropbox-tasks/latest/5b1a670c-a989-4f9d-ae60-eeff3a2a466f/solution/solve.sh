#!/bin/bash
set -euo pipefail

# Explore Composer/Phinx package + cutover register, then install corrected modules
head -n 40 /workspace/iris-provenance/composer.json
ls -1 /workspace/iris-provenance/vendor/bin | sort
ls -1 /workspace/iris-provenance/db/migrations | sort
head -n 20 /workspace/iris-provenance/phinx.php
cat /workspace/docs/handover-index.md
sed -n '1,120p' /workspace/docs/provenance-binding.md
head -n 80 /workspace/docs/module-cutover-policy/volume-3-register-tokens.md
head -n 40 /workspace/docs/module-cutover-policy/volume-1-qualification.md
head -n 40 /workspace/docs/module-cutover-policy/volume-2-emit-rules.md
head -n 30 /workspace/docs/archive/legacy-normalize-notes.md
cat /workspace/config/cutover-register.json
cat /workspace/config/archive-cutover-register.json
cat /workspace/config/paths.json
head -n 40 /workspace/data/proxy-exports/iris-gateway-provenance.json
sed -n '1,80p' /workspace/schemas/normalized-graph.schema.json
head -n 40 /workspace/iris-provenance/src/Normalize/ProxyNormalizer.php
head -n 40 /workspace/iris-provenance/src/Export/DigestExporter.php
head -n 20 /workspace/iris-provenance/scripts/verify-provenance.sh

mkdir -p /workspace/output /workspace/state
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
install -d /workspace/iris-provenance/bin
install -d /workspace/iris-provenance/src/Normalize
install -d /workspace/iris-provenance/src/Cli
install -d /workspace/iris-provenance/src/Support
install -d /workspace/iris-provenance/src/Load
install -d /workspace/iris-provenance/src/Export
install -d /workspace/iris-provenance/db/migrations
install -d /workspace/iris-provenance/scripts
cp "$SCRIPT_DIR"/bin/iris-prov /workspace/iris-provenance/bin/
cp "$SCRIPT_DIR"/src/Normalize/ProxyNormalizer.php /workspace/iris-provenance/src/Normalize/
cp "$SCRIPT_DIR"/src/Cli/Application.php /workspace/iris-provenance/src/Cli/
cp "$SCRIPT_DIR"/src/Support/JsonWriter.php /workspace/iris-provenance/src/Support/
cp "$SCRIPT_DIR"/src/Load/GraphLoader.php /workspace/iris-provenance/src/Load/
cp "$SCRIPT_DIR"/src/Export/DigestExporter.php /workspace/iris-provenance/src/Export/
cp "$SCRIPT_DIR"/db/migrations/*.php /workspace/iris-provenance/db/migrations/
cp "$SCRIPT_DIR"/scripts/verify-provenance.sh /workspace/iris-provenance/scripts/
chmod +x /workspace/iris-provenance/bin/iris-prov /workspace/iris-provenance/scripts/verify-provenance.sh

php /workspace/iris-provenance/bin/iris-prov normalize \
  --export /workspace/data/proxy-exports/iris-gateway-provenance.json \
  --paths /workspace/config/paths.json \
  --out /workspace/output/normalized-graph.json

php /workspace/iris-provenance/bin/iris-prov migrate \
  --graph /workspace/output/normalized-graph.json \
  --paths /workspace/config/paths.json

php /workspace/iris-provenance/bin/iris-prov export-digest \
  --paths /workspace/config/paths.json

bash /workspace/iris-provenance/scripts/verify-provenance.sh
