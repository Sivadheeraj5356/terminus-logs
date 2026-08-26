#!/usr/bin/env bash
set -euo pipefail
# Restores visible demo spool layout when seed-data is mounted at /data
SEED="${SPECZ_SEED:-/data}"
for d in inbox work archive quarantine state/results; do
  mkdir -p "${SEED}/${d}"
done
rm -f "${SEED}"/inbox/*.spz "${SEED}"/work/*.processing 2>/dev/null || true
rm -f "${SEED}"/archive/* "${SEED}"/quarantine/* 2>/dev/null || true
rm -f "${SEED}"/state/manifest.tsv "${SEED}"/state/results/*.json 2>/dev/null || true
rm -f /output/drift.jsonl 2>/dev/null || true
# Copy from bundled seed if present
BUNDLE="${SPECZ_VISIBLE_SEED:-/seed-data}"
if [[ -d "$BUNDLE" ]]; then
  cp -a "$BUNDLE"/inbox/*.spz "${SEED}/inbox/" 2>/dev/null || true
  cp -a "$BUNDLE"/work/*.processing "${SEED}/work/" 2>/dev/null || true
  cp -a "$BUNDLE"/state/manifest.tsv "${SEED}/state/" 2>/dev/null || true
  cp -a "$BUNDLE"/state/results/*.json "${SEED}/state/results/" 2>/dev/null || true
fi
echo "visible spool reset complete"
