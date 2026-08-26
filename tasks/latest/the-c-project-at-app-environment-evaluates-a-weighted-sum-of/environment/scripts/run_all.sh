#!/usr/bin/env bash
set -euo pipefail

cd /app/environment
make clean >/dev/null
make >/dev/null
mkdir -p outputs

manifest="${THETA_CASES:-data/cases.csv}"
data_dir="${THETA_DATA_DIR:-.}"

first=1
while IFS=, read -r name case_path; do
    if [ "$first" = "1" ]; then
        first=0
        continue
    fi
    case_path="${case_path%$'\r'}"
    [ -z "$name" ] && continue
    ./theta "$data_dir/$case_path" "outputs/$name.txt"
done < "$manifest"
