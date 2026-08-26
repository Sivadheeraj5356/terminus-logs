#!/usr/bin/env bash
# Run the submitted Rego policy against the DuckDB facts for a single
# workstation and print the resulting plan as JSON on stdout.
#
# Usage: run_policy.sh <workstation_id>
#
# Reads: /app/policy/*.rego (submitted by the agent)
# Query:  data.workstation.plan.actions
# Output: {"workstation_id": "...", "actions": [...]}
#
# Non-zero exit means either the fact load failed, OPA rejected the policy,
# or `actions` is not defined.  The verifier keys off the exit code AND the
# emitted JSON, so both must be well-formed for a passing plan.
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "usage: $0 <workstation_id>" >&2
    exit 2
fi
WS_ID="$1"
POLICY_DIR="/app/policy"

if ! ls "${POLICY_DIR}"/*.rego >/dev/null 2>&1; then
    echo "no .rego files found under ${POLICY_DIR}" >&2
    exit 4
fi

FACTS_JSON="$(python3 /app/harness/load_facts.py "${WS_ID}")"

# opa eval with -d loading every rego file under the policy dir, stdin as input.
RAW="$(printf '%s' "${FACTS_JSON}" | \
    opa eval -f json -I -d "${POLICY_DIR}" 'data.workstation.plan.actions')"

# Extract the actions array; fail cleanly if the rule is undefined.
ACTIONS="$(printf '%s' "${RAW}" | jq -c '.result[0].expressions[0].value // empty')"
if [ -z "${ACTIONS}" ] || [ "${ACTIONS}" = "null" ]; then
    echo "policy did not produce data.workstation.plan.actions for ${WS_ID}" >&2
    echo "opa raw output: ${RAW}" >&2
    exit 5
fi

# Wrap with the workstation id so downstream diffs are self-describing.
jq -cn --arg id "${WS_ID}" --argjson actions "${ACTIONS}" \
    '{workstation_id: $id, actions: $actions}'
