#!/usr/bin/env bash
set -euo pipefail

cat > /app/solve.sh <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail

records=/app/records
out=/app/dossier
rm -rf "$out"
mkdir -p "$out/decision" "$out/evidence" "$out/attestations" "$out/index"

declare -A incident host_pri host_group health_status health_epoch cred_group cred_nb cred_na cred_rev
declare -A svc_pri svc_mount svc_route svc_cred svc_barrier deps lease_holder lease_epoch lease_fence
declare -A mount_volume mount_owner route_scope route_host rb

while IFS=$'\t' read -r key value; do
  [[ "$key" == "key" ]] && continue
  incident[$key]=$value
done < "$records/incident.tsv"
epoch=${incident[incident_epoch]}
root=${incident[root_service]}
old=${incident[old_active_host]}
threshold=${incident[quorum_threshold]}

while IFS=$'\t' read -r host priority group; do
  [[ "$host" == "host_id" ]] && continue
  host_pri[$host]=$priority
  host_group[$host]=$group
done < "$records/hosts.tsv"

while IFS=$'\t' read -r host status ev; do
  [[ "$host" == "host_id" ]] && continue
  health_status[$host]=$status
  health_epoch[$host]=$ev
done < "$records/health.tsv"

while IFS=$'\t' read -r svc priority mount route cred barrier; do
  [[ "$svc" == "service_id" ]] && continue
  svc_pri[$svc]=$priority
  svc_mount[$svc]=$mount
  svc_route[$svc]=$route
  svc_cred[$svc]=$cred
  svc_barrier[$svc]=$barrier
done < "$records/services.tsv"

while IFS=$'\t' read -r svc dep; do
  [[ "$svc" == "service_id" ]] && continue
  deps[$svc]="${deps[$svc]:-} $dep"
done < "$records/dependencies.tsv"

while IFS=$'\t' read -r cred group nb na revoked; do
  [[ "$cred" == "credential_id" ]] && continue
  cred_group[$cred]=$group
  cred_nb[$cred]=$nb
  cred_na[$cred]=$na
  cred_rev[$cred]=$revoked
done < "$records/credentials.tsv"

while IFS=$'\t' read -r vol holder authority state ev fence; do
  [[ "$vol" == "volume_id" ]] && continue
  lease_holder[$vol]=$holder
  lease_epoch[$vol]=$ev
  lease_fence[$vol]=$fence
done < "$records/leases.tsv"

while IFS=$'\t' read -r svc vol owner; do
  [[ "$svc" == "service_id" ]] && continue
  mount_volume[$svc]=$vol
  mount_owner[$svc]=$owner
done < "$records/mounts.tsv"

while IFS=$'\t' read -r svc scope host; do
  [[ "$svc" == "service_id" ]] && continue
  route_scope[$svc]=$scope
  route_host[$svc]=$host
done < "$records/routes.tsv"

while IFS=$'\t' read -r old_destroyed route_rollback storage_reattach; do
  [[ "$old_destroyed" == "old_host_destroyed" ]] && continue
  rb[old_host_destroyed]=$old_destroyed
  rb[route_rollback]=$route_rollback
  rb[storage_reattach]=$storage_reattach
done < "$records/rollback.tsv"

current_health() {
  local host=$1
  if [[ "${health_epoch[$host]:-}" == "$epoch" ]]; then
    printf '%s' "${health_status[$host]:-MISSING}"
  else
    printf 'MISSING'
  fi
}

eligible_host() {
  local st
  st=$(current_health "$1")
  [[ "$st" == "UP" || "$st" == "DEGRADED" ]]
}

quorum_count() {
  local cand=$1 count=0
  while IFS=$'\t' read -r c voter reachable ev; do
    [[ "$c" == "candidate_host" ]] && continue
    if [[ "$c" == "$cand" && "$ev" == "$epoch" && "$reachable" == "YES" && -n "${host_pri[$voter]:-}" ]]; then
      [[ "$(current_health "$voter")" == "DOWN" || "$(current_health "$voter")" == "MISSING" ]] || count=$((count + 1))
    fi
  done < "$records/quorum.tsv"
  printf '%s' "$count"
}

selected=""
while IFS=$'\t' read -r host priority group; do
  [[ "$host" == "host_id" || "$host" == "$old" ]] && continue
  if eligible_host "$host" && [[ "$(quorum_count "$host")" -ge "$threshold" ]]; then
    selected=$host
    break
  fi
done < <(tail -n +2 "$records/hosts.tsv" | sort -t $'\t' -k2,2n -k1,1)

{
  printf 'host_id\tstatus\tcurrent\teligible\n'
  for h in "${!host_pri[@]}"; do
    st=$(current_health "$h")
    current=NO
    [[ "${health_epoch[$h]:-}" == "$epoch" ]] && current=YES
    elig=NO
    [[ "$h" != "$old" ]] && eligible_host "$h" && elig=YES
    printf '%s\t%s\t%s\t%s\n' "$h" "$st" "$current" "$elig"
  done | sort
} > "$out/evidence/health-ledger.tsv"

{
  printf 'candidate_host\treachable_votes\tthreshold\tquorum_status\n'
  for h in "${!host_pri[@]}"; do
    [[ "$h" == "$old" ]] && continue
    count=$(quorum_count "$h")
    status=FAIL
    [[ "$count" -ge "$threshold" ]] && status=PASS
    printf '%s\t%s\t%s\t%s\n' "$h" "$count" "$threshold" "$status"
  done | sort
} > "$out/evidence/quorum-ledger.tsv"

declare -A cred_status fence_status mount_status started held hold_reason
target_group=NONE
[[ -n "$selected" ]] && target_group=${host_group[$selected]}

printf 'service_id\tcredential_id\tcredential_status\n' > "$out/evidence/credential-ledger.tsv"
while IFS=$'\t' read -r s pri mount route cred barrier; do
  [[ "$s" == "service_id" ]] && continue
  c=${svc_cred[$s]}
  status=FAIL
  if [[ "${cred_rev[$c]:-YES}" == "NO" && "${cred_group[$c]:-}" == "$target_group" && "$epoch" -ge "${cred_nb[$c]:-999999}" && "$epoch" -le "${cred_na[$c]:-0}" ]]; then
    status=PASS
  fi
  cred_status[$s]=$status
  printf '%s\t%s\t%s\n' "$s" "$c" "$status" >> "$out/evidence/credential-ledger.tsv"
done < <(tail -n +2 "$records/services.tsv" | sort -t $'\t' -k1,1)

printf 'volume_id\tprevious_holder\tfence_status\n' > "$out/evidence/fencing-ledger.tsv"
while IFS=$'\t' read -r s vol prev; do
  [[ "$s" == "service_id" ]] && continue
  status=FAIL
  if [[ "$prev" == "$selected" ]]; then
    status=NOT_NEEDED
  elif [[ "${lease_epoch[$vol]:-}" == "$epoch" && "${lease_fence[$vol]:-NO}" == "YES" ]]; then
    status=FENCED
  fi
  fence_status[$vol]=$status
  printf '%s\t%s\t%s\n' "$vol" "$prev" "$status" >> "$out/evidence/fencing-ledger.tsv"
done < <(tail -n +2 "$records/mounts.tsv" | sort -t $'\t' -k2,2)

printf 'service_id\tvolume_id\ttarget_host\tmount_status\n' > "$out/evidence/mount-ledger.tsv"
while IFS=$'\t' read -r s vol prev; do
  [[ "$s" == "service_id" ]] && continue
  status=FAIL
  [[ "${fence_status[$vol]:-FAIL}" == "FENCED" || "${fence_status[$vol]:-FAIL}" == "NOT_NEEDED" ]] && status=PASS
  mount_status[$s]=$status
  printf '%s\t%s\t%s\t%s\n' "$s" "$vol" "$selected" "$status" >> "$out/evidence/mount-ledger.tsv"
done < <(tail -n +2 "$records/mounts.tsv" | sort -t $'\t' -k1,1)

progress=1
while [[ "$progress" -eq 1 ]]; do
  progress=0
  while IFS=$'\t' read -r s pri mount route cred barrier; do
    [[ "$s" == "service_id" || -n "${started[$s]:-}" || -n "${held[$s]:-}" ]] && continue
    reason=""
    [[ "${cred_status[$s]:-FAIL}" != "PASS" ]] && reason=CREDENTIAL_BLOCKED
    [[ -z "$reason" && "$mount" != "NONE" && "${mount_status[$s]:-FAIL}" != "PASS" ]] && reason=MOUNT_BLOCKED
    if [[ -z "$reason" ]]; then
      for dep in ${deps[$s]:-}; do
        [[ -n "${held[$dep]:-}" ]] && reason=DEPENDENCY_HELD
        [[ -z "${started[$dep]:-}" ]] && reason=${reason:-DEPENDENCY_HELD}
      done
    fi
    if [[ -z "$reason" && "${svc_route[$s]}" != "internal" && ( -z "${route_scope[$s]:-}" || "${route_scope[$s]}" != "${svc_route[$s]}" ) ]]; then
      reason=ROUTE_BLOCKED
    fi
    if [[ -n "$reason" ]]; then
      held[$s]=1
      hold_reason[$s]=$reason
      progress=1
    else
      ready=YES
      for dep in ${deps[$s]:-}; do
        [[ -z "${started[$dep]:-}" ]] && ready=NO
      done
      if [[ "$ready" == "YES" ]]; then
        started[$s]=1
        progress=1
      fi
    fi
  done < <(tail -n +2 "$records/services.tsv" | sort -t $'\t' -k2,2n -k1,1)
done

{
  printf 'order\tservice_id\ttarget_host\n'
  n=1
  while IFS=$'\t' read -r s pri mount route cred barrier; do
    [[ "$s" == "service_id" ]] && continue
    if [[ -n "${started[$s]:-}" ]]; then
      printf '%s\t%s\t%s\n' "$n" "$s" "$selected"
      n=$((n + 1))
    fi
  done < <(tail -n +2 "$records/services.tsv" | sort -t $'\t' -k2,2n -k1,1)
} > "$out/decision/start-order.tsv"

{
  printf 'service_id\treason\n'
  for s in "${!held[@]}"; do
    printf '%s\t%s\n' "$s" "${hold_reason[$s]}"
  done | sort
} > "$out/decision/hold-list.tsv"

{
  printf 'service_id\tadvertised_host\tadvertised_scope\troute_status\n'
  for s in "${!svc_pri[@]}"; do
    if [[ -n "${held[$s]:-}" && "${hold_reason[$s]:-}" == "ROUTE_BLOCKED" ]]; then
      printf '%s\t%s\t%s\tFAIL\n' "$s" "$selected" "${route_scope[$s]:-NONE}"
    elif [[ -n "${held[$s]:-}" ]]; then
      printf '%s\tNONE\tNONE\tHELD\n' "$s"
    elif [[ "${svc_route[$s]}" == "internal" ]]; then
      printf '%s\tNONE\tinternal\tPASS\n' "$s"
    elif [[ -z "${route_scope[$s]:-}" || "${route_scope[$s]}" != "${svc_route[$s]}" ]]; then
      printf '%s\t%s\t%s\tFAIL\n' "$s" "$selected" "${route_scope[$s]:-NONE}"
    else
      printf '%s\t%s\t%s\tPASS\n' "$s" "$selected" "${route_scope[$s]:-${svc_route[$s]}}"
    fi
  done | sort
} > "$out/evidence/route-ledger.tsv"

rollback_status=AVAILABLE
rollback_blockers=()
[[ "${rb[old_host_destroyed]:-YES}" == "NO" ]] || rollback_blockers+=("OLD_HOST_DESTROYED")
[[ "${rb[route_rollback]:-NO}" == "YES" ]] || rollback_blockers+=("ROUTE_ROLLBACK_BLOCKED")
[[ "${rb[storage_reattach]:-NO}" == "YES" ]] || rollback_blockers+=("STORAGE_REATTACH_BLOCKED")
for s in "${!started[@]}"; do
  [[ "${svc_barrier[$s]}" == "YES" ]] && rollback_blockers+=("IRREVERSIBLE_SERVICE:$s")
done
[[ "${#rollback_blockers[@]}" -gt 0 ]] && rollback_status=BLOCKED

printf '{\n  "blockers": [' > "$out/decision/rollback-window.json"
if [[ "${#rollback_blockers[@]}" -gt 0 ]]; then
  IFS=$'\n' sorted=($(printf '%s\n' "${rollback_blockers[@]}" | sort)); unset IFS
  printf '\n' >> "$out/decision/rollback-window.json"
  for i in "${!sorted[@]}"; do
    [[ "$i" -gt 0 ]] && printf ',\n' >> "$out/decision/rollback-window.json"
    printf '    "%s"' "${sorted[$i]}" >> "$out/decision/rollback-window.json"
  done
  printf '\n  ' >> "$out/decision/rollback-window.json"
fi
printf '],\n  "rollback_status": "%s",\n  "target_host": "%s"\n}\n' "$rollback_status" "$selected" >> "$out/decision/rollback-window.json"

verdict=NO_SAFE_FAILOVER
blocker=NONE
if [[ -z "$selected" ]]; then
  any_healthy=NO
  for h in "${!host_pri[@]}"; do
    [[ "$h" == "$old" ]] && continue
    eligible_host "$h" && any_healthy=YES
  done
  if [[ "$any_healthy" == "YES" ]]; then
    blocker=QUORUM_BLOCKED
  else
    blocker=NO_HEALTHY_TARGET
  fi
else
  if awk -F '\t' 'NR>1 && $3=="FAIL" {bad=1} END{exit bad?0:1}' "$out/evidence/fencing-ledger.tsv"; then
    blocker=FENCING_BLOCKED
  elif awk -F '\t' 'NR>1 && $4=="FAIL" {bad=1} END{exit bad?0:1}' "$out/evidence/mount-ledger.tsv"; then
    blocker=MOUNT_BLOCKED
  elif [[ -z "${started[$root]:-}" ]]; then
    blocker=${hold_reason[$root]:-DEPENDENCY_HELD}
  elif awk -F '\t' 'NR>1 && $4=="FAIL" {bad=1} END{exit bad?0:1}' "$out/evidence/route-ledger.tsv"; then
    blocker=ROUTE_BLOCKED
  elif [[ "$rollback_status" != "AVAILABLE" ]]; then
    blocker=ROLLBACK_BLOCKED
  else
    verdict=FAILOVER_READY
  fi
fi

cat > "$out/decision/failover-verdict.json" <<JSON
{
  "earliest_blocker": "$blocker",
  "incident_epoch": $epoch,
  "old_active_host": "$old",
  "root_service": "$root",
  "target_host": "$selected",
  "verdict": "$verdict"
}
JSON

attest() {
  local name=$1 status=$2 evidence=$3
  cat > "$out/attestations/$name" <<JSON
{
  "evidence": "$evidence",
  "incident_epoch": $epoch,
  "status": "$status",
  "target_host": "$selected"
}
JSON
}

attest dependency-attestation.json PASS "decision/start-order.tsv;decision/hold-list.tsv;evidence/credential-ledger.tsv;evidence/mount-ledger.tsv"
qstatus=$(awk -F '\t' -v t="$selected" 'NR>1 && $1==t {print $4}' "$out/evidence/quorum-ledger.tsv")
[[ -z "$qstatus" ]] && qstatus=FAIL
attest quorum-attestation.json "$qstatus" "evidence/quorum-ledger.tsv;evidence/health-ledger.tsv"
fstatus=PASS
awk -F '\t' 'NR>1 && $3=="FAIL" {bad=1} END{exit bad?0:1}' "$out/evidence/fencing-ledger.tsv" && fstatus=FAIL
attest fencing-attestation.json "$fstatus" "evidence/fencing-ledger.tsv;evidence/mount-ledger.tsv"
rstatus=PASS
awk -F '\t' 'NR>1 && $4=="FAIL" {bad=1} END{exit bad?0:1}' "$out/evidence/route-ledger.tsv" && rstatus=FAIL
attest route-attestation.json "$rstatus" "evidence/route-ledger.tsv;decision/hold-list.tsv"
attest rollback-attestation.json "$rollback_status" "decision/rollback-window.json;evidence/route-ledger.tsv;evidence/mount-ledger.tsv"

{
  printf '{\n  "artifact_count": 16,\n  "artifacts": {\n'
  first=1
  while IFS= read -r file; do
    rel=${file#"$out/"}
    [[ "$rel" == "index/incident-index.json" ]] && continue
    hash=$(sha256sum "$file" | awk '{print $1}')
    [[ "$first" -eq 0 ]] && printf ',\n'
    first=0
    printf '    "%s": "%s"' "$rel" "$hash"
  done < <(find "$out" -type f | sort)
  printf '\n  },\n  "dependency_edges": [\n'
  first_edge=1
  emit_edge() {
    [[ "$first_edge" -eq 0 ]] && printf ',\n'
    first_edge=0
    printf '    [\n      "%s",\n      "%s"\n    ]' "$1" "$2"
  }
  for rel in $(find "$out" -type f | sed "s#^$out/##" | sort); do
    [[ "$rel" == "index/incident-index.json" ]] && continue
    emit_edge "index/incident-index.json" "$rel"
  done
  emit_edge "attestations/dependency-attestation.json" "decision/start-order.tsv"
  emit_edge "attestations/dependency-attestation.json" "decision/hold-list.tsv"
  emit_edge "attestations/fencing-attestation.json" "evidence/fencing-ledger.tsv"
  emit_edge "attestations/quorum-attestation.json" "evidence/quorum-ledger.tsv"
  emit_edge "attestations/rollback-attestation.json" "decision/rollback-window.json"
  emit_edge "attestations/route-attestation.json" "evidence/route-ledger.tsv"
  emit_edge "decision/failover-verdict.json" "attestations/quorum-attestation.json"
  emit_edge "decision/failover-verdict.json" "attestations/fencing-attestation.json"
  printf '\n'
  printf '  ],\n  "incident_epoch": %s,\n  "root_service": "%s",\n  "target_host": "%s",\n  "verdict": "%s"\n}\n' "$epoch" "$root" "$selected" "$verdict"
} > "$out/index/incident-index.json"
SCRIPT

chmod +x /app/solve.sh
/app/solve.sh
