#!/bin/bash
# build and run over the sample ruleset/flows. handy while iterating.
set -euo pipefail
cd "$(dirname "$0")/.."
go build -o bin/acl ./cmd/acl
./bin/acl evaluate --rules testdata/rules_main.json --flows testdata/flows_main.ndjson
echo '--- lint ---'
./bin/acl lint --rules testdata/rules_main.json --flows testdata/flows_main.ndjson
