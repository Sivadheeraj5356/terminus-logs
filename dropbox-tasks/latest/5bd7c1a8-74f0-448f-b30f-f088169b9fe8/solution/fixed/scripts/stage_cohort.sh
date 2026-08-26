#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: stage_cohort.sh DATASET WORK_DIR LABEL_COLUMN" >&2
  exit 1
fi

DATASET="$1"
WORK_DIR="$2"
LABEL_COLUMN="$3"
STAGED="${WORK_DIR}/cohort_staged.csv"

if [[ ! -f "$DATASET" ]]; then
  echo "dataset not found: ${DATASET}" >&2
  exit 1
fi

header="$(head -n 1 "$DATASET")"
IFS=',' read -r -a columns <<< "$header"

found_id=false
found_label=false
for raw in "${columns[@]}"; do
  col="$(echo "$raw" | tr -d '[:space:]')"
  if [[ "$col" == "id" ]]; then
    found_id=true
  fi
  if [[ "$col" == "$LABEL_COLUMN" ]]; then
    found_label=true
  fi
done

if [[ "$found_id" != true || "$found_label" != true ]]; then
  echo "missing required columns in header" >&2
  exit 2
fi

mkdir -p "$WORK_DIR"
cp "$DATASET" "$STAGED"
