#!/usr/bin/env bash
#
# Convenience harness for exercising the triage module against a corpus.
# This is a developer aid, not the grader. Usage:
#
#   integration/run_triage.sh <corpus_dir> [output_dir] [severity_gate] [salt]
#
# It applies the module and prints the resulting report. A gated corpus makes
# `terraform apply` exit non-zero (that is expected behavior), but the report is
# still written and shown.
set -u

MODULE_DIR="$(cd "$(dirname "$0")/../triage" && pwd)"
CORPUS_DIR="${1:?usage: run_triage.sh <corpus_dir> [output_dir] [gate] [salt]}"
OUT_DIR="${2:-$MODULE_DIR/out}"
GATE="${3:-high}"
SALT="${4:-vaultseal}"

terraform -chdir="$MODULE_DIR" init -input=false -no-color >/dev/null

terraform -chdir="$MODULE_DIR" apply -auto-approve -input=false -no-color \
  -var "corpus_dir=$CORPUS_DIR" \
  -var "output_dir=$OUT_DIR" \
  -var "severity_gate=$GATE" \
  -var "redaction_salt=$SALT"
APPLY_RC=$?

REPORT="$OUT_DIR/triage_report.json"
echo "----- apply exit code: $APPLY_RC -----"
if [ -f "$REPORT" ]; then
  echo "----- $REPORT -----"
  cat "$REPORT"
else
  echo "no report produced at $REPORT"
fi
