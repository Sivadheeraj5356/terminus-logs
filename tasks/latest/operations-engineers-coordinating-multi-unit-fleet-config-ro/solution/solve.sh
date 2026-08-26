#!/bin/bash
# Oracle — organizational-decision-impact-planner fleet rollout planner
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
FILES="${ROOT_DIR}/files"

install -m 0644 "${FILES}/internal/decyclose/cycle_engine.go" /app/internal/decyclose/cycle_engine.go
install -m 0644 "${FILES}/internal/unitfan/propagate.go" /app/internal/unitfan/propagate.go
install -m 0644 "${FILES}/internal/gatechain/roles.go" /app/internal/gatechain/roles.go
install -m 0644 "${FILES}/internal/poolclash/detect.go" /app/internal/poolclash/detect.go
install -m 0644 "${FILES}/internal/cleargate/clearance.go" /app/internal/cleargate/clearance.go
install -m 0644 "${FILES}/internal/epochseal/seal.go" /app/internal/epochseal/seal.go
install -m 0644 "${FILES}/internal/rolljournal/journal.go" /app/internal/rolljournal/journal.go
install -m 0644 "${FILES}/internal/supersede/gate.go" /app/internal/supersede/gate.go
install -m 0644 "${FILES}/internal/slotbind/digest.go" /app/internal/slotbind/digest.go

test -s /app/internal/decyclose/cycle_engine.go
test -s /app/internal/unitfan/propagate.go
test -s /app/internal/gatechain/roles.go
test -s /app/internal/poolclash/detect.go
test -s /app/internal/cleargate/clearance.go
test -s /app/internal/epochseal/seal.go
test -s /app/internal/rolljournal/journal.go
test -s /app/internal/supersede/gate.go
test -s /app/internal/slotbind/digest.go

grep -q 'package decyclose' /app/internal/decyclose/cycle_engine.go
grep -q 'package unitfan' /app/internal/unitfan/propagate.go
grep -q 'package gatechain' /app/internal/gatechain/roles.go
grep -q 'package poolclash' /app/internal/poolclash/detect.go
grep -q 'package cleargate' /app/internal/cleargate/clearance.go
grep -q 'package epochseal' /app/internal/epochseal/seal.go
grep -q 'package rolljournal' /app/internal/rolljournal/journal.go
grep -q 'package supersede' /app/internal/supersede/gate.go
grep -q 'package slotbind' /app/internal/slotbind/digest.go

grep -q 'DetectCycle' /app/internal/decyclose/cycle_engine.go
grep -q 'FanOut' /app/internal/unitfan/propagate.go
grep -q 'BuildSteps' /app/internal/gatechain/roles.go
grep -q 'FindConflicts' /app/internal/poolclash/detect.go
grep -q 'RegulatoryBlocks' /app/internal/cleargate/clearance.go
grep -q 'ComputeSeal' /app/internal/epochseal/seal.go
grep -q 'LatestForScenario' /app/internal/rolljournal/journal.go
grep -q 'func Allow' /app/internal/supersede/gate.go
grep -q 'WindowDigest' /app/internal/slotbind/digest.go
grep -q 'BookingDigest' /app/internal/slotbind/digest.go

mkdir -p /app/bin /app/state/odip /app/output
rm -f /app/state/odip/rollout_journal.jsonl
cd /app
CGO_ENABLED=0 go build -o /app/bin/odip ./cmd/odip
test -x /app/bin/odip

/app/bin/odip run \
  --scenario /app/fixtures/scenarios/budget_realloc \
  --policy /app/fixtures/policies/approval_policy.json \
  --stage /app/state/odip/impact_lattice.json \
  --out /app/output/decision_impact_plan.json

test -s /app/state/odip/impact_lattice.json
test -s /app/output/decision_impact_plan.json
test -s /app/state/odip/rollout_journal.jsonl
grep -q 'odip.lattice.v1' /app/state/odip/impact_lattice.json
grep -q 'odip.plan.v1' /app/output/decision_impact_plan.json
grep -q 'epoch_seal' /app/output/decision_impact_plan.json
grep -q 'window_digest' /app/output/decision_impact_plan.json
grep -q 'booking_digest' /app/output/decision_impact_plan.json
grep -q 'budget_realloc' /app/state/odip/rollout_journal.jsonl
