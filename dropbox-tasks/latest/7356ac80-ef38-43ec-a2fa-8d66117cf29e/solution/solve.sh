#!/bin/bash
set -o errexit
set -o nounset
set -o pipefail

readonly app_root=/app
readonly submitted_source=/solution/main.cpp

deploy_interrupter_source() {
    local destination="$app_root/src/main.cpp"
    install -m 0644 "$submitted_source" "$destination"
}

rebuild_interrupter_cli() {
    rm -f "$app_root/arcguard"
    make -C "$app_root" --always-make arcguard
    test -x "$app_root/arcguard"
}

deploy_interrupter_source
rebuild_interrupter_cli
