#!/bin/bash
# Quick tour of the modverse CLI against the bundled sample registry.
set -euo pipefail

/app/app/build.sh

echo "== compare two versions =="
modverse version --compare v1.4.0-rc.2 v1.4.0

echo "== sort a version list =="
modverse version --sort v2.0.0,v1.0.0,v1.0.0-rc.1

echo "== parse a manifest =="
modverse manifest --file /app/app/sample-registry/main.mod

echo "== build list =="
modverse buildlist --registry /app/app/sample-registry --main /app/app/sample-registry/main.mod

echo "== build list plus loaded manifests =="
modverse graph --registry /app/app/sample-registry --main /app/app/sample-registry/main.mod
