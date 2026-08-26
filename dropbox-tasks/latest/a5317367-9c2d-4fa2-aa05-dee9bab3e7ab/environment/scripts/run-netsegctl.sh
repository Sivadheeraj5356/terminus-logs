#!/usr/bin/env bash
set -euo pipefail

STAGE="${1:-all}"
ENV_ROOT="${ENV_ROOT:-/app/environment}"
OUTPUT_ROOT="${OUTPUT_ROOT:-/app/output}"
export ENV_ROOT OUTPUT_ROOT

LIB="$ENV_ROOT/scripts/lib"

run_stage() {
  local name="$1"
  case "$name" in
    vlan-check) bash "$LIB/vlan_check.sh" ;;
    trunk-check) bash "$LIB/trunk_check.sh" ;;
    acl-check) bash "$LIB/acl_check.sh" ;;
    render) bash "$LIB/render.sh" ;;
    wave-plan) bash "$LIB/wave_plan.sh" ;;
    rollback-audit) bash "$LIB/rollback_audit.sh" ;;
    evidence) bash "$LIB/evidence.sh" ;;
    all)
      # Binding spine: VLAN → trunk → ACL(from VRF) → render → wave → rollback → evidence
      bash "$LIB/vlan_check.sh"
      bash "$LIB/trunk_check.sh"
      bash "$LIB/acl_check.sh"
      bash "$LIB/render.sh"
      bash "$LIB/wave_plan.sh"
      bash "$LIB/rollback_audit.sh"
      bash "$LIB/evidence.sh"
      ;;
    *)
      echo "unknown stage: $name" >&2
      echo "usage: run-netsegctl.sh [vlan-check|trunk-check|acl-check|render|wave-plan|rollback-audit|evidence|all]" >&2
      exit 2
      ;;
  esac
}

run_stage "$STAGE"
