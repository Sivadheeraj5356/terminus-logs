#!/usr/bin/env bash
set -euo pipefail

cd /app/environment
make clean >/dev/null
make >/dev/null
mkdir -p outputs

manifest="${ERFSUM_CASES:-data/cases.csv}"
data_dir="${ERFSUM_DATA_DIR:-.}"

first=1
while IFS=, read -r name input_path; do
    if [ "$first" = "1" ]; then
        first=0
        continue
    fi
    [ -z "$name" ] && continue
    ./erfsum "$data_dir/$input_path" "outputs/$name.txt"
done < "$manifest"
