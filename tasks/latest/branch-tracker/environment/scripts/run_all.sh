#!/usr/bin/env bash
set -euo pipefail

cd /app/environment
make clean >/dev/null
make >/dev/null
mkdir -p outputs

manifest="${CONT_CASES:-data/cases.csv}"
data_dir="${CONT_DATA_DIR:-.}"

first=1
while IFS=, read -r name contract_path; do
    if [ "$first" = "1" ]; then
        first=0
        continue
    fi
    contract_path="${contract_path%$'\r'}"
    [ -z "$name" ] && continue
    ./tracecurve "$data_dir/$contract_path" "outputs/$name.txt"
done < "$manifest"
