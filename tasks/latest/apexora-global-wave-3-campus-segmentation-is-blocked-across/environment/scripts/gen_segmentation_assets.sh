#!/usr/bin/env bash
# One-time fleet asset generator for Apexora SegmentFirst Wave 3 environment.
# Authoring scaffolding only — generates infrastructure configs, not agent code.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# ── Constants ──────────────────────────────────────────────────────────────
ASN=65000
VRFS=(
  CORP-IT FINANCE HR PAYROLL MFG-OT MFG-IT SCADA GUEST GUEST-WIFI DMZ DMZ-PUB
  PCI VOICE VIDEO MGMT IDENTITY BACKUP REPLICATION LAB DEV QA STAGING VENDOR
  PARTNER LOGISTICS WAREHOUSE RETAIL BUILDING-AUTO EMERGENCY TELEMED
)
SEGMENTS=(corp finance hr mfg ot guest dmz pci voice video mgmt lab vendor retail logistics)

CAMPUS_IDS=(campus-hq-dal campus-amw-sea campus-emea-lon campus-emea-fra campus-apac-sin campus-apac-tyo)
CAMPUS_LABELS=(HQ-DAL AMW-SEA EMEA-LON EMEA-FRA APAC-SIN APAC-TYO)
CAMPUS_REGIONS=(amer amer emea emea apac apac)
ACCESS_COUNTS=(14 10 8 7 7 6)
DIST_COUNTS=(3 2 2 2 3 2)
CORE_COUNTS=(1 1 1 1 1 1)
ROUTER_COUNTS=(4 3 4 3 5 5)

# ── Helpers ──────────────────────────────────────────────────────────────────
migration_state_for() {
  local role="$1" campus_idx="$2" seq="$3"
  local campus="${CAMPUS_IDS[$campus_idx]}"
  case "$campus" in
    campus-emea-fra|campus-apac-tyo) echo legacy ;;
    campus-amw-sea)
      if [[ "$role" == "access" && $((seq % 3)) -eq 0 ]]; then echo legacy
      elif [[ "$role" == "dist" && $seq -eq 1 ]]; then echo partial
      else echo segmented; fi ;;
    campus-apac-sin)
      if [[ "$role" == "access" ]]; then echo partial
      elif [[ "$role" == "dist" ]]; then echo segmented
      else echo partial; fi ;;
    campus-hq-dal)
      if [[ "$role" == "access" && $seq -le 2 ]]; then echo partial
      elif [[ "$role" == "core" && $seq -eq 2 ]]; then echo partial
      else echo segmented; fi ;;
    campus-emea-lon)
      if [[ "$role" == "access" && $seq -eq 7 ]]; then echo partial
      elif [[ "$role" == "dist" && $seq -eq 2 ]]; then echo partial
      else echo segmented; fi ;;
    *)
      echo segmented ;;
  esac
}

canonical_vlan_id() { echo $((2000 + $1)); }
legacy_vlan_id()    { echo $((100 + ($1 % 80) + 1)); }

vrf_for_vlan() {
  local idx="$1"
  echo "${VRFS[$((idx % ${#VRFS[@]}))]}"
}

write_vrf_catalog() {
  mkdir -p vrfs/definitions vrfs/campus_route_targets
  cat > vrfs/catalog.yaml <<'HDR'
schema_version: apexora-vrf-catalog-1
program: segmentfirst-wave-3
vrf_count: 30
vrfs:
HDR
  local i=0
  for vrf in "${VRFS[@]}"; do
    local rd=$((65000 + i))
    local rt=$((1000 + i))
    cat >> vrfs/catalog.yaml <<EOF
  ${vrf}:
    rd: "${rd}:$(printf '%04d' "$rt")"
    rt_export: "${rd}:$(printf '%04d' "$rt")"
    rt_import: ["${rd}:$(printf '%04d' "$rt")"]
    gateway_tier: distribution
    default_acl_profile: SEG-${vrf}-IN
    qos_class: $( [[ "$vrf" == "VOICE" || "$vrf" == "VIDEO" ]] && echo EF || echo AF31 )
EOF
    cat > "vrfs/definitions/${vrf}.yaml" <<EOF
schema_version: apexora-vrf-def-1
vrf_name: ${vrf}
description: Apexora ${vrf} macro-segment
rd: "${rd}:$(printf '%04d' "$rt")"
rt_export: "${rd}:$(printf '%04d' "$rt")"
rt_import:
  - "${rd}:$(printf '%04d' "$rt")"
route_distinguisher_note: unique per VRF per segmentation_contract
inter_vrf_leak: false
EOF
    i=$((i + 1))
  done

  for region in amer emea apac; do
    cat > "vrfs/campus_route_targets/${region}.yaml" <<EOF
schema_version: apexora-vrf-rt-region-1
region: ${region}
route_targets:
EOF
    for vrf in "${VRFS[@]}"; do
      echo "  - vrf: ${vrf}" >> "vrfs/campus_route_targets/${region}.yaml"
    done
  done

  cat > vrfs/leak_exceptions.yaml <<'EOF'
schema_version: apexora-vrf-leak-1
exceptions:
  - source_vrf: MGMT
    destination_vrf: CORP-IT
    route_prefixes: ["10.250.0.0/16"]
    dossier_section: gateway-leak-mgmt-corp
    status: ACTIVE
  - source_vrf: IDENTITY
    destination_vrf: CORP-IT
    route_prefixes: ["10.251.0.0/16"]
    dossier_section: gateway-leak-identity-corp
    status: ACTIVE
EOF
}

write_vlan_catalog() {
  mkdir -p vlans/campuses
  cat > vlans/catalog.yaml <<'HDR'
schema_version: apexora-vlan-catalog-1
vlan_count: 180
vlans:
HDR
  cat > vlans/segment_map.yaml <<'HDR'
schema_version: apexora-vlan-segment-1
segments:
HDR
  cat > vlans/legacy_id_map.yaml <<'HDR'
schema_version: apexora-vlan-legacy-map-1
legacy_to_canonical:
HDR

  local seg_idx=0
  for i in $(seq 1 180); do
    local cid=$(canonical_vlan_id "$i")
    local lid=$(legacy_vlan_id "$i")
    local seg="${SEGMENTS[$((seg_idx % ${#SEGMENTS[@]}))]}"
    local vrf=$(vrf_for_vlan "$i")
    local campus="${CAMPUS_IDS[$((i % 6))]}"
    local name="$(echo "$seg" | tr '[:lower:]' '[:upper:]')-$(printf '%03d' "$i")"
    cat >> vlans/catalog.yaml <<EOF
  - id: ${cid}
    name: ${name}
    segment: ${seg}
    vrf: ${vrf}
    campus: ${campus}
    legacy_id: ${lid}
EOF
    echo "  ${seg}: ${cid}" >> vlans/segment_map.yaml
    echo "  ${lid}: ${cid}" >> vlans/legacy_id_map.yaml
    seg_idx=$((seg_idx + 1))
  done

  for ci in "${!CAMPUS_IDS[@]}"; do
    local campus="${CAMPUS_IDS[$ci]}"
    cat > "vlans/campuses/${campus}.yaml" <<EOF
schema_version: apexora-vlan-campus-1
campus: ${campus}
allowed_vlan_range: 2001-2180
local_vlan_count: 30
vlans:
EOF
    for i in $(seq 1 30); do
      local vid=$((2000 + ci * 30 + i))
      [[ $vid -gt 2180 ]] && continue
      echo "  - id: ${vid}" >> "vlans/campuses/${campus}.yaml"
    done
  done
}

write_acl_catalog() {
  mkdir -p acl/object_groups acl/profiles acl/device_bindings
  cat > acl/catalog.yaml <<'HDR'
schema_version: apexora-acl-catalog-1
policy_count: 90
policies:
HDR
  local n=1
  for vrf in "${VRFS[@]}"; do
    for dir in IN OUT; do
      [[ $n -gt 90 ]] && break 2
      cat >> acl/catalog.yaml <<EOF
  - id: SEG-${vrf}-${dir}-$(printf '%04d' "$n")
    name: SEG-${vrf}-${dir}
    type: extended
    direction: $(echo "$dir" | tr '[:upper:]' '[:lower:]')
    vrf: ${vrf}
    status: active
    object_group: OG-SEG-${vrf}
EOF
      n=$((n + 1))
    done
  done
  # pad to 90 if needed
  while [[ $n -le 90 ]]; do
    cat >> acl/catalog.yaml <<EOF
  - id: SEG-MISC-$(printf '%04d' "$n")
    name: SEG-MISC-POLICY-${n}
    type: extended
    direction: inbound
    vrf: CORP-IT
    status: active
    object_group: OG-SEG-CORP
EOF
    n=$((n + 1))
  done

  cat > acl/object_groups/address_catalog.yaml <<'EOF'
schema_version: apexora-addr-og-1
object_groups:
  OG-SEG-CORP:
    - 10.200.0.0/16
    - 10.201.0.0/16
  OG-SEG-FINANCE:
    - 10.210.0.0/16
  OG-SEG-HR:
    - 10.211.0.0/16
  OG-SEG-GUEST:
    - 10.230.0.0/16
  OG-SEG-DMZ:
    - 10.240.0.0/16
  OG-SEG-MGMT:
    - 10.250.0.0/16
  OG-SEG-OT:
    - 10.220.0.0/16
EOF

  cat > acl/object_groups/service_catalog.yaml <<'EOF'
schema_version: apexora-svc-og-1
object_groups:
  OG-SVC-WEB:
    - tcp 443
    - tcp 8443
  OG-SVC-DNS:
    - udp 53
    - tcp 53
  OG-SVC-AD:
    - tcp 389
    - tcp 636
    - udp 88
  OG-SVC-SIP:
    - udp 5060
    - tcp 5061
EOF

  for profile in finance_enclave hr_enclave guest_captive ot_isolation dmz_edge; do
    cat > "acl/profiles/${profile}.yaml" <<EOF
schema_version: apexora-acl-profile-1
profile: ${profile}
inbound_acl: SEG-$(echo "$profile" | tr '[:lower:]' '[:upper:]' | cut -d_ -f1)-IN
outbound_acl: SEG-$(echo "$profile" | tr '[:lower:]' '[:upper:]' | cut -d_ -f1)-OUT
EOF
  done

  cat > acl/device_bindings/distribution_acl_map.yaml <<'EOF'
schema_version: apexora-dist-acl-bind-1
bindings:
  dist-hq-dal-main-01:
    Vlan2101: SEG-FINANCE-IN
  dist-emea-fra-main-01:
    Vlan2101: ACL-INSIDE-ANY
EOF

  cat > acl/device_bindings/router_edge_acl_map.yaml <<'EOF'
schema_version: apexora-edge-acl-bind-1
bindings:
  rtr-hq-dal-edge-01:
    GigabitEthernet0/0/1: SEG-DMZ-IN
  rtr-apac-tyo-edge-01:
    GigabitEthernet0/0/0: ACL-EDGE-LEGACY
EOF

  mkdir -p acl/rules
  local n=1
  for vrf in "${VRFS[@]}"; do
    for dir in IN OUT; do
      [[ $n -gt 90 ]] && break 2
      local legacy_name=""
      [[ $((n % 7)) -eq 0 ]] && legacy_name="! legacy alias: ACL-FLAT-$(printf '%03d' "$n")"
      cat > "acl/rules/SEG-${vrf}-${dir}.conf" <<EOF
! Extended ACL — SEG-${vrf}-${dir}
${legacy_name}
ip access-list extended SEG-${vrf}-${dir}
 remark Apexora segmentation policy ${n}
 permit object-group OG-SEG-${vrf%%-*} tcp any any eq 443
 permit object-group OG-SVC-DNS udp any any eq 53
 deny   ip any any log
EOF
      n=$((n + 1))
    done
  done
  while [[ $n -le 90 ]]; do
    cat > "acl/rules/SEG-MISC-POLICY-${n}.conf" <<EOF
! Extended ACL — SEG-MISC-POLICY-${n}
ip access-list extended SEG-MISC-POLICY-${n}
 remark Miscellaneous segmentation policy
 permit tcp any any established
 deny ip any any
EOF
    n=$((n + 1))
  done

  cat > acl/rules/ACL-INSIDE-ANY.conf <<'EOF'
! DEPRECATED legacy ACL — do not reference post-migration
ip access-list extended ACL-INSIDE-ANY
 remark Flat network inside any
 permit ip any any
EOF

  cat > acl/rules/ACL-EDGE-LEGACY.conf <<'EOF'
! DEPRECATED legacy edge ACL
ip access-list extended ACL-EDGE-LEGACY
 remark Flat network edge
 permit ip any any
EOF
}

write_qos_catalog() {
  mkdir -p qos/class_maps qos/policy_maps qos/device_bindings
  cat > qos/bandwidth_profiles.yaml <<'EOF'
schema_version: apexora-qos-bw-1
profiles:
  corp_standard:
    cir_mbps: 1000
    shape_average: 950000000
  voice_priority:
    cir_mbps: 100
    shape_average: 100000000
  guest_best_effort:
    cir_mbps: 200
    shape_average: 150000000
  ot_scada:
    cir_mbps: 50
    shape_average: 45000000
  wan_edge_aggregate:
    cir_mbps: 500
    shape_average: 480000000
EOF

  local maps=(corp_it voice_video guest_best_effort ot_scada wan_edge)
  local i=1
  for m in "${maps[@]}"; do
    cat > "qos/class_maps/${m}.yaml" <<EOF
schema_version: apexora-qos-class-1
class_map: CM-${m^^}
match:
  - dscp af31
  - vlan $(canonical_vlan_id "$i")
EOF
    cat > "qos/policy_maps/${m}.yaml" <<EOF
schema_version: apexora-qos-policy-1
policy_map: PM-${m^^}
classes:
  - class: CM-${m^^}
    bandwidth_percent: 30
    queue_limit: 8192
EOF
    i=$((i + 1))
  done
  # pad policy maps to 25 total policies
  for j in $(seq 6 20); do
    cat > "qos/class_maps/extra_${j}.yaml" <<EOF
schema_version: apexora-qos-class-1
class_map: CM-EXTRA-${j}
match:
  - dscp cs${j}
EOF
    cat > "qos/policy_maps/extra_${j}.yaml" <<EOF
schema_version: apexora-qos-policy-1
policy_map: PM-EXTRA-${j}
classes:
  - class: CM-EXTRA-${j}
    bandwidth_percent: 5
EOF
  done

  cat > qos/device_bindings/dist_qos_map.yaml <<'EOF'
schema_version: apexora-qos-dist-bind-1
bindings:
  dist-hq-dal-main-01:
    TenGigabitEthernet1/1/1: PM-CORP_IT
  dist-emea-fra-main-01:
    TenGigabitEthernet1/1/1: PM-LEGACY-BE
EOF

  cat > qos/device_bindings/router_qos_map.yaml <<'EOF'
schema_version: apexora-qos-router-bind-1
bindings:
  rtr-hq-dal-edge-01:
    GigabitEthernet0/0/0: PM-WAN_EDGE
EOF

  mkdir -p qos/policies
  local q=1
  while [[ $q -le 25 ]]; do
    cat > "qos/policies/QOS-POLICY-$(printf '%03d' "$q").yaml" <<EOF
schema_version: apexora-qos-policy-entry-1
policy_id: QOS-POLICY-$(printf '%03d' "$q")
policy_map: PM-POLICY-${q}
class_map: CM-POLICY-${q}
description: Campus segmentation QoS policy ${q}
trust_dscp: true
queue_limit_packets: 8192
EOF
    q=$((q + 1))
  done
}

write_interfaces_and_trunks() {
  mkdir -p interfaces/gateway interfaces/trunk interfaces/wan interfaces/port_profiles
  mkdir -p trunks/policies trunks/assignments

  cat > interfaces/gateway/gateway_bindings.yaml <<'EOF'
schema_version: apexora-gateway-bind-1
bindings:
  - vlan_id: 2101
    vrf: FINANCE
    primary: dist-hq-dal-main-01
    secondary: dist-hq-dal-main-02
    vip: 10.210.1.1
  - vlan_id: 2102
    vrf: HR
    primary: dist-hq-dal-main-01
    secondary: dist-hq-dal-main-02
    vip: 10.211.1.1
  - vlan_id: 2120
    vrf: GUEST
    primary: dist-emea-fra-main-01
    secondary: dist-emea-fra-main-02
    vip: 10.230.1.1
EOF

  cat > interfaces/gateway/hsrp_profiles.yaml <<'EOF'
schema_version: apexora-hsrp-1
profiles:
  finance_dist:
    group: 101
    priority_primary: 110
    priority_secondary: 100
    preempt: true
  hr_dist:
    group: 102
    priority_primary: 110
    priority_secondary: 100
    preempt: true
EOF

  cat > interfaces/trunk/trunk_policy.yaml <<'EOF'
schema_version: apexora-trunk-policy-1
policies:
  access_to_dist:
    mode: selective
    max_vlan_span: 12
    forbidden: [1, 1002-1005]
  dist_to_core:
    mode: selective
    max_vlan_span: 40
  core_interconnect:
    mode: selective
    max_vlan_span: 80
EOF

  cat > interfaces/wan/wan_bindings.yaml <<'EOF'
schema_version: apexora-wan-bind-1
bindings:
  rtr-hq-dal-edge-01:
    GigabitEthernet0/0/0:
      vrf: CORP-IT
      provider: MPLS-PE-01
  rtr-emea-fra-edge-01:
    GigabitEthernet0/0/0:
      vrf: VRF-CORP
      provider: MPLS-PE-02
EOF

  cat > interfaces/wan/mpls_handoff.yaml <<'EOF'
schema_version: apexora-mpls-handoff-1
handoffs:
  - router: rtr-hq-dal-edge-01
    interface: GigabitEthernet0/0/0.100
    pe: 192.0.2.1
    vrf: CORP-IT
EOF

  for p in access_user access_ot dist_uplink core_interconnect; do
    cat > "interfaces/port_profiles/${p}.yaml" <<EOF
schema_version: apexora-port-profile-1
profile: ${p}
switchport_mode: $( [[ "$p" == access_* ]] && echo access || echo trunk )
EOF
  done

  for pol in access_to_dist dist_to_core core_intercampus; do
    cat > "trunks/policies/${pol}.yaml" <<EOF
schema_version: apexora-trunk-pol-1
policy: ${pol}
allowed_mode: selective
native_vlan: 999
EOF
  done

  cat > trunks/violations_seed.yaml <<'EOF'
schema_version: apexora-trunk-violations-1
violations:
  - device: acc-emea-fra-lab-01
    interface: TenGigabitEthernet1/1/1
    issue: trunk_all_vlans
  - device: core-apac-sin-01
    interface: TenGigabitEthernet1/1/2
    issue: over_permissive_allowed_vlan
EOF
}

write_inventory() {
  mkdir -p inventory
  cat > inventory/campus_index.yaml <<'EOF'
schema_version: apexora-campus-1
campuses:
  - id: campus-hq-dal
    region: amer
    buildings: [bldg1, bldg2, bldg3, dc-wing]
  - id: campus-amw-sea
    region: amer
    buildings: [plant-a, plant-b, admin]
  - id: campus-emea-lon
    region: emea
    buildings: [tower-a, tower-b]
  - id: campus-emea-fra
    region: emea
    buildings: [lab, office, ot-yard]
  - id: campus-apac-sin
    region: apac
    buildings: [hub, guest-wing]
  - id: campus-apac-tyo
    region: apac
    buildings: [office, mfg]
EOF

  cat > inventory/device_inventory.yaml <<'HDR'
schema_version: apexora-device-inventory-1
device_count: 96
devices:
HDR

  cat > inventory/uplink_graph.yaml <<'HDR'
schema_version: apexora-uplink-1
links:
HDR

  cat > inventory/vlan_assignments.yaml <<'HDR'
schema_version: apexora-vlan-assign-1
assignments:
HDR

  cat > inventory/vrf_bindings.yaml <<'HDR'
schema_version: apexora-vrf-bind-1
bindings:
HDR

  cat > inventory/audit_findings.yaml <<'HDR'
schema_version: apexora-audit-1
findings:
HDR
}

append_device() {
  local hostname="$1" role="$2" campus="$3" state="$4" platform="$5"
  cat >> inventory/device_inventory.yaml <<EOF
  - hostname: ${hostname}
    role: ${role}
    campus_id: ${campus}
    platform: ${platform}
    migration_state: ${state}
EOF
}

gen_access_switch() {
  local campus="$1" campus_short="$2" bldg="$3" seq="$4" campus_idx="$5"
  local host="acc-${campus_short}-${bldg}-$(printf '%02d' "$seq")"
  local state
  state=$(migration_state_for access "$campus_idx" "$seq")
  local dir="switches/access/${host}"
  mkdir -p "${dir}/interfaces"

  local vlan_idx=$(( (campus_idx * 10 + seq) % 180 + 1 ))
  local canon=$(canonical_vlan_id "$vlan_idx")
  local legacy=$(legacy_vlan_id "$vlan_idx")
  local use_vlan=$canon
  local acl_ref="SEG-CORP-IT-IN"
  local trunk_mode="switchport trunk allowed vlan ${canon},$((canon+1)),$((canon+2))"

  case "$state" in
    legacy)
      use_vlan=$legacy
      acl_ref="ACL-INSIDE-ANY"
      trunk_mode="switchport trunk allowed vlan all"
      ;;
    partial)
      use_vlan=$legacy
      acl_ref="OG-FLAT-USER"
      ;;
  esac

  append_device "$host" access "$campus" "$state" "ios-xe"

  cat > "${dir}/running.conf" <<EOF
! ${host} — Cisco IOS-XE access switch
! Apexora SegmentFirst Wave 3
! migration_state: ${state}
version 17.9
hostname ${host}
!
no service pad
service timestamps debug datetime msec localtime show-timezone
service timestamps log datetime msec localtime show-timezone
!
spanning-tree mode rapid-pvst
spanning-tree extend system-id
!
vlan internal allocation policy ascending
vlan ${canon}
 name SEG-$(printf '%03d' "$vlan_idx")
vlan ${legacy}
 name LEGACY-FLAT-$(printf '%03d' "$vlan_idx")
!
interface GigabitEthernet1/0/1
 description User access port — building ${bldg}
 switchport mode access
 switchport access vlan ${use_vlan}
 spanning-tree portfast
 spanning-tree bpduguard enable
 ip access-group ${acl_ref} in
!
interface GigabitEthernet1/0/2
 description User access port
 switchport mode access
 switchport access vlan ${use_vlan}
 spanning-tree portfast
!
interface TenGigabitEthernet1/1/1
 description Uplink to distribution
 ${trunk_mode}
 switchport trunk native vlan 999
 switchport mode trunk
!
interface Vlan${use_vlan}
 description LEGACY-SVI-ON-ACCESS — remove during segmentation
 ip address 10.$((200 + campus_idx)).$seq.1 255.255.255.0
 no ip redirects
!
ip default-gateway 10.$((200 + campus_idx)).0.1
!
line con 0
 logging synchronous
line vty 0 4
 transport input ssh
!
EOF

  cat > "${dir}/vlan.local.yaml" <<EOF
hostname: ${host}
migration_state: ${state}
canonical_vlan: ${canon}
configured_vlan: ${use_vlan}
legacy_vlan: ${legacy}
duplicate_vlan_conflict: $( [[ "$state" == "legacy" && $((seq % 4)) -eq 0 ]] && echo true || echo false )
EOF

  cat > "${dir}/interfaces/Gi1_0_3.conf" <<EOF
interface GigabitEthernet1/0/3
 description Conference room access
 switchport mode access
 switchport access vlan $((use_vlan + 1))
EOF

  cat > "${dir}/interfaces/Gi1_0_4.conf" <<EOF
interface GigabitEthernet1/0/4
 description Printer access
 switchport mode access
 switchport access vlan $((use_vlan + 2))
EOF

  cat > "${dir}/interfaces/Lo0.conf" <<EOF
interface Loopback0
 description ${host} management loopback
 ip address 10.255.99.${campus_idx}${seq} 255.255.255.255
EOF

  cat > "${dir}/interfaces/Gi1_0_1.conf" <<EOF
interface GigabitEthernet1/0/1
 switchport access vlan ${use_vlan}
EOF

  cat > "${dir}/interfaces/Te1_1_1_uplink.conf" <<EOF
interface TenGigabitEthernet1/1/1
 ${trunk_mode}
 switchport mode trunk
EOF

  echo "  - uplink: ${host} -> dist-${campus_short}-main-01" >> inventory/uplink_graph.yaml
  echo "  ${host}: [${canon}, $((canon+1))]" >> inventory/vlan_assignments.yaml
  echo "  ${host}: CORP-IT" >> inventory/vrf_bindings.yaml

  if [[ "$state" != "segmented" ]]; then
    cat >> inventory/audit_findings.yaml <<EOF
  - hostname: ${host}
    codes: [$( [[ "$state" == "legacy" ]] && echo "legacy_vlan_ids_present,trunk_all_vlans" || echo "partial_vlan_mapping" )]
EOF
  fi
}

gen_dist_switch() {
  local campus="$1" campus_short="$2" seq="$3" campus_idx="$4"
  local host="dist-${campus_short}-main-$(printf '%02d' "$seq")"
  local state
  state=$(migration_state_for dist "$campus_idx" "$seq")
  local dir="switches/distribution/${host}"
  mkdir -p "${dir}/interfaces"

  local vlan_base=$((2100 + campus_idx * 10 + seq))
  local vip="10.$((210 + campus_idx)).${seq}.1"
  local acl="SEG-FINANCE-IN"
  [[ "$state" == "legacy" ]] && acl="ACL-INSIDE-ANY"
  [[ "$state" == "partial" ]] && acl="OG-FLAT-FINANCE"

  append_device "$host" distribution "$campus" "$state" "ios-xe"

  cat > "${dir}/running.conf" <<EOF
! ${host} — Cisco IOS-XE distribution switch
! migration_state: ${state}
version 17.9
hostname ${host}
!
ip routing
ip vrf CORP-IT
 rd ${ASN}:$(printf '%04d' $((1000 + campus_idx)))
 route-target export ${ASN}:$(printf '%04d' $((1000 + campus_idx)))
 route-target import ${ASN}:$(printf '%04d' $((1000 + campus_idx)))
!
ip vrf FINANCE
 rd ${ASN}:$(printf '%04d' $((1100 + campus_idx)))
 route-target export ${ASN}:$(printf '%04d' $((1100 + campus_idx)))
 route-target import ${ASN}:$(printf '%04d' $((1100 + campus_idx)))
!
interface Vlan${vlan_base}
 description Finance gateway SVI
 ip vrf forwarding FINANCE
 ip address ${vip} 255.255.255.0
 standby 10 ip ${vip}
 standby 10 priority $( [[ $seq -eq 1 ]] && echo 110 || echo 100 )
 ip access-group ${acl} in
!
interface TenGigabitEthernet1/1/1
 description Uplink to core
 switchport trunk allowed vlan 2001-2180
 switchport mode trunk
!
interface TenGigabitEthernet1/1/2
 description Downlink to access
 switchport trunk allowed vlan $( [[ "$state" == "legacy" ]] && echo "all" || echo "${vlan_base}-$((vlan_base+20))" )
 switchport mode trunk
!
router ospf 1 vrf FINANCE
 network 10.$((210 + campus_idx)).0.0 0.0.255.255 area 0
!
EOF

  cat > "${dir}/svi.conf" <<EOF
interface Vlan${vlan_base}
 ip vrf forwarding FINANCE
 ip address ${vip} 255.255.255.0
 standby 10 ip ${vip}
EOF

  cat > "${dir}/interfaces/Te1_1_2_downlink.conf" <<EOF
interface TenGigabitEthernet1/1/2
 description Downlink to access layer
 switchport trunk allowed vlan ${vlan_base}-$((vlan_base+20))
 switchport mode trunk
EOF

  cat > "${dir}/interfaces/Lo0.conf" <<EOF
interface Loopback0
 ip address 10.255.${campus_idx}.${seq} 255.255.255.255
EOF

  cat > "${dir}/interfaces/Vlan${vlan_base}.conf" <<EOF
interface Vlan${vlan_base}
 ip vrf forwarding FINANCE
 ip address ${vip} 255.255.255.0
EOF

  echo "  - uplink: ${host} -> core-${campus_short}-01" >> inventory/uplink_graph.yaml
}

gen_core_switch() {
  local campus="$1" campus_short="$2" seq="$3" campus_idx="$4"
  local host="core-${campus_short}-$(printf '%02d' "$seq")"
  local state
  state=$(migration_state_for core "$campus_idx" "$seq")
  local dir="switches/core/${host}"
  mkdir -p "${dir}/interfaces"

  append_device "$host" core "$campus" "$state" "ios-xe"

  cat > "${dir}/running.conf" <<EOF
! ${host} — Cisco IOS-XE core switch
! migration_state: ${state}
version 17.9
hostname ${host}
!
ip routing
!
interface TenGigabitEthernet1/1/1
 description Core fabric link
 switchport trunk allowed vlan 2001-2180
 switchport mode trunk
!
interface TenGigabitEthernet1/1/2
 description To distribution
 switchport trunk allowed vlan $( [[ "$state" == "partial" ]] && echo "2001-2099,3001-3099" || echo "2001-2180" )
 switchport mode trunk
!
interface Loopback0
 ip address 10.255.${campus_idx}.${seq} 255.255.255.255
!
router ospf 1
 network 10.255.${campus_idx}.0.0 0.0.255.255 area 0
!
EOF

  cat > "${dir}/interfaces/core_fabric.conf" <<EOF
interface TenGigabitEthernet1/1/1
 switchport trunk allowed vlan 2001-2180
 switchport mode trunk
EOF
}

gen_router() {
  local campus="$1" campus_short="$2" seq="$3" campus_idx="$4"
  local host="rtr-${campus_short}-edge-$(printf '%02d' "$seq")"
  local state=segmented
  case "${CAMPUS_IDS[$campus_idx]}" in
    campus-emea-fra|campus-apac-tyo) state=legacy ;;
    campus-amw-sea) [[ $seq -eq 1 ]] && state=partial || state=segmented ;;
    campus-apac-sin) [[ $seq -le 2 ]] && state=partial || state=segmented ;;
    campus-hq-dal) [[ $seq -eq 4 ]] && state=partial || state=segmented ;;
  esac

  local dir="routers/${campus}/${host}"
  mkdir -p "${dir}/interfaces"

  local vrf="CORP-IT"
  local legacy_vrf="VRF-CORP"
  local use_vrf=$vrf
  [[ "$state" == "legacy" || "$state" == "partial" ]] && use_vrf=$legacy_vrf

  append_device "$host" wan_edge "$campus" "$state" "ios-xe"

  cat > "${dir}/running.conf" <<EOF
! ${host} — Cisco IOS-XE WAN edge router
! migration_state: ${state}
version 17.9
hostname ${host}
!
ip vrf ${vrf}
 rd ${ASN}:$(printf '%04d' $((2000 + campus_idx * 10 + seq)))
 route-target export ${ASN}:$(printf '%04d' $((2000 + campus_idx * 10 + seq)))
 route-target import ${ASN}:$(printf '%04d' $((2000 + campus_idx * 10 + seq)))
!
ip vrf FINANCE
 rd ${ASN}:$(printf '%04d' $((2100 + campus_idx * 10 + seq)))
!
interface Loopback0
 ip vrf forwarding ${use_vrf}
 ip address 10.254.${campus_idx}.${seq} 255.255.255.255
!
interface GigabitEthernet0/0/0
 description MPLS PE handoff
 ip vrf forwarding ${use_vrf}
 ip address 192.0.2.$((campus_idx * 10 + seq)) 255.255.255.252
 ip access-group $( [[ "$state" == "legacy" ]] && echo "ACL-EDGE-LEGACY" || echo "SEG-DMZ-IN" ) in
 service-policy output PM-WAN_EDGE
!
interface GigabitEthernet0/0/0.100
 description CORP L3VPN subinterface
 encapsulation dot1Q 100
 ip vrf forwarding ${use_vrf}
 ip address 10.200.${campus_idx}.${seq} 255.255.255.252
!
interface GigabitEthernet0/0/1
 description DMZ handoff
 ip vrf forwarding DMZ
 ip address 10.240.${campus_idx}.${seq} 255.255.255.252
!
router bgp ${ASN}
 bgp router-id 10.254.${campus_idx}.${seq}
 address-family ipv4 vrf ${use_vrf}
  redistribute connected
  neighbor 192.0.2.$((campus_idx * 10 + seq - 1)) remote-as 65001
  neighbor 192.0.2.$((campus_idx * 10 + seq - 1)) activate
 exit-address-family
!
EOF

  cat > "${dir}/vrf.conf" <<EOF
ip vrf ${use_vrf}
 rd ${ASN}:$(printf '%04d' $((2000 + campus_idx * 10 + seq)))
EOF

  cat > "${dir}/interfaces/Gi0_0_2_transit.conf" <<EOF
interface GigabitEthernet0/0/2
 description Core transit link
 ip vrf forwarding ${use_vrf}
 ip address 10.199.${campus_idx}.${seq} 255.255.255.252
EOF

  cat > "${dir}/interfaces/Lo0.conf" <<EOF
interface Loopback0
 ip vrf forwarding ${use_vrf}
 ip address 10.254.${campus_idx}.${seq} 255.255.255.255
EOF

  cat > "${dir}/interfaces/Gi0_0_0_mpls_pe.conf" <<EOF
interface GigabitEthernet0/0/0
 ip vrf forwarding ${use_vrf}
 ip address 192.0.2.$((campus_idx * 10 + seq)) 255.255.255.252
EOF

  cat > "${dir}/interfaces/Gi0_0_1_dmz.conf" <<EOF
interface GigabitEthernet0/0/1
 ip vrf forwarding DMZ
 ip address 10.240.${campus_idx}.${seq} 255.255.255.252
EOF
}

gen_trunk_assignments() {
  local link_count=0
  for ci in "${!CAMPUS_IDS[@]}"; do
    local campus="${CAMPUS_IDS[$ci]}"
    local short=$(echo "$campus" | sed 's/campus-//')
    cat > "trunks/assignments/${campus}_trunks.yaml" <<EOF
schema_version: apexora-trunk-assign-1
campus: ${campus}
trunk_links:
EOF
    local acc="${ACCESS_COUNTS[$ci]}"
    local dist="${DIST_COUNTS[$ci]}"
    for s in $(seq 1 "$acc"); do
      echo "  - id: TRK-$(printf '%04d' $((link_count+1)))" >> "trunks/assignments/${campus}_trunks.yaml"
      echo "    a: acc-${short}-bldg1-$(printf '%02d' "$s")" >> "trunks/assignments/${campus}_trunks.yaml"
      echo "    b: dist-${short}-main-01" >> "trunks/assignments/${campus}_trunks.yaml"
      echo "    allowed: selective" >> "trunks/assignments/${campus}_trunks.yaml"
      link_count=$((link_count + 1))
    done
    for d in $(seq 1 "$dist"); do
      echo "  - id: TRK-$(printf '%04d' $((link_count+1)))" >> "trunks/assignments/${campus}_trunks.yaml"
      echo "    a: dist-${short}-main-$(printf '%02d' "$d")" >> "trunks/assignments/${campus}_trunks.yaml"
      echo "    b: core-${short}-01" >> "trunks/assignments/${campus}_trunks.yaml"
      echo "    allowed: selective" >> "trunks/assignments/${campus}_trunks.yaml"
      link_count=$((link_count + 1))
    done
  done
  # pad trunk link metadata in a manifest
  cat > trunks/link_manifest.yaml <<EOF
schema_version: apexora-trunk-manifest-1
trunk_link_count: ${link_count}
target_count: 140
note: additional inter-core and inter-campus trunks defined in campus assignments
EOF
  # generate remaining trunk records to reach ~140
  mkdir -p trunks/links
  for t in $(seq 1 140); do
    cat > "trunks/links/TRK-$(printf '%04d' "$t").yaml" <<EOF
schema_version: apexora-trunk-link-1
trunk_id: TRK-$(printf '%04d' "$t")
endpoint_a: device-$(printf '%03d' "$((t % 72 + 1))")
endpoint_b: device-$(printf '%03d' "$((t % 72 + 2))")
allowed_vlans: selective
native_vlan: 999
migration_state: $( [[ $((t % 5)) -eq 0 ]] && echo legacy || echo segmented )
EOF
  done
}

write_fleet() {
  write_inventory
  for ci in "${!CAMPUS_IDS[@]}"; do
    local campus="${CAMPUS_IDS[$ci]}"
    local short=$(echo "$campus" | sed 's/campus-//')
    local bldgs=(bldg1 bldg2 bldg3)
    [[ "$campus" == "campus-hq-dal" ]] && bldgs=(bldg1 bldg2 bldg3 dc-wing)
    [[ "$campus" == "campus-amw-sea" ]] && bldgs=(plant-a plant-b admin)
    [[ "$campus" == "campus-emea-lon" ]] && bldgs=(tower-a tower-b)
    [[ "$campus" == "campus-emea-fra" ]] && bldgs=(lab office ot-yard)
    [[ "$campus" == "campus-apac-sin" ]] && bldgs=(hub guest-wing)
    [[ "$campus" == "campus-apac-tyo" ]] && bldgs=(office mfg)

    local acc="${ACCESS_COUNTS[$ci]}"
    local seq=1
    while [[ $seq -le $acc ]]; do
      local bldg="${bldgs[$(((seq - 1) % ${#bldgs[@]}))]}"
      gen_access_switch "$campus" "$short" "$bldg" "$seq" "$ci"
      seq=$((seq + 1))
    done

    for d in $(seq 1 "${DIST_COUNTS[$ci]}"); do
      gen_dist_switch "$campus" "$short" "$d" "$ci"
    done

    for c in $(seq 1 "${CORE_COUNTS[$ci]}"); do
      gen_core_switch "$campus" "$short" "$c" "$ci"
    done

    for r in $(seq 1 "${ROUTER_COUNTS[$ci]}"); do
      gen_router "$campus" "$short" "$r" "$ci"
    done
  done
  gen_trunk_assignments
}

write_legacy() {
  mkdir -p legacy/gateway_on_access legacy/hooks
  cat > legacy/vlan_map_flat.csv <<'EOF'
legacy_id,legacy_name,flat_segment
110,FLAT-USERS,users
120,FLAT-SERVERS,servers
130,FLAT-VOICE,voice
140,FLAT-GUEST,guest
150,FLAT-OT,ot
EOF
  cat > legacy/acl_names.txt <<'EOF'
ACL-INSIDE-ANY
ACL-OUTSIDE-ANY
ACL-EDGE-LEGACY
OG-FLAT-USER
OG-FLAT-FINANCE
OG-FLAT-SERVER
EOF
  cat > legacy/trunk-all.conf.fragment <<'EOF'
! DEPRECATED — flat network trunk template
interface TenGigabitEthernet1/1/1
 switchport trunk allowed vlan all
 switchport mode trunk
EOF
  cat > legacy/gateway_on_access/acc-legacy-svi.conf.fragment <<'EOF'
! DEPRECATED — SVI on access layer
interface Vlan110
 ip address 10.1.110.1 255.255.255.0
EOF
  cat > legacy/hooks/pre-validate-legacy.sh <<'EOF'
#!/usr/bin/env bash
# DEPRECATED — flat network validation hook
echo "legacy-validate-ok"
EOF
  chmod +x legacy/hooks/pre-validate-legacy.sh
}

write_deployment() {
  mkdir -p deployment/waves deployment/canary deployment/rollback deployment/hooks deployment/validation
  cat > deployment/waves/wave_3.yaml <<'EOF'
schema_version: apexora-wave-1
wave_id: wave_3
canary_first: true
regional_order: [amer, emea, apac]
phases:
  - phase_id: canary
    campuses: [campus-hq-dal]
    devices: [acc-hq-dal-bldg1-01, dist-hq-dal-main-01]
  - phase_id: amer_batch
    region: amer
    campuses: [campus-hq-dal, campus-amw-sea]
  - phase_id: emea_batch
    region: emea
    campuses: [campus-emea-lon, campus-emea-fra]
  - phase_id: apac_batch
    region: apac
    campuses: [campus-apac-sin, campus-apac-tyo]
post_deploy_hook: services/hooks/post-validate.sh
legacy_hooks_present: true
EOF

  cat > deployment/canary/groups.yaml <<'EOF'
schema_version: apexora-canary-1
groups:
  - name: hq_canary
    required_devices:
      - acc-hq-dal-bldg1-01
      - dist-hq-dal-main-01
    gate:
      validation_hook: legacy/hooks/pre-validate-legacy.sh
EOF

  cat > deployment/rollback/bundles.yaml <<'EOF'
schema_version: apexora-rollback-1
bundles:
  acc-hq-dal-bldg1-01:
    forward: switches/access/acc-hq-dal-bldg1-01/running.conf
    rollback: backups/pre_wave3/acc-hq-dal-bldg1-01.conf.snapshot
    validation_command: legacy/hooks/pre-validate-legacy.sh
EOF

  cat > deployment/hooks/post_validate.conf <<'EOF'
active_hook: services/hooks/post-validate.sh
deprecated_hooks:
  - legacy/hooks/pre-validate-legacy.sh
EOF

  for probe in vlan trunk gateway acl; do
    cat > "deployment/validation/${probe}_probes.yaml" <<EOF
schema_version: apexora-${probe}-probe-1
probes:
  - name: ${probe}_catalog_match
  - name: ${probe}_no_legacy_source
EOF
  done
}

write_templates() {
  mkdir -p templates/ios-xe templates/hsrp templates/trunk templates/acl
  cat > templates/ios-xe/access_base.conf <<'EOF'
! IOS-XE access switch baseline
version 17.9
spanning-tree mode rapid-pvst
spanning-tree portfast default
spanning-tree bpduguard default
EOF
  cat > templates/ios-xe/dist_base.conf <<'EOF'
! IOS-XE distribution baseline
version 17.9
ip routing
EOF
  cat > templates/ios-xe/core_base.conf <<'EOF'
! IOS-XE core baseline
version 17.9
ip routing
EOF
  cat > templates/ios-xe/ce_router_base.conf <<'EOF'
! IOS-XE CE router baseline
version 17.9
EOF
  cat > templates/hsrp/dist_primary.conf.template <<'EOF'
standby {{GROUP}} ip {{VIP}}
standby {{GROUP}} priority 110
standby {{GROUP}} preempt
EOF
  cat > templates/trunk/selective_trunk.conf.template <<'EOF'
switchport trunk allowed vlan {{VLAN_LIST}}
switchport mode trunk
switchport trunk native vlan 999
EOF
  cat > templates/acl/svi_inbound.conf.template <<'EOF'
ip access-group {{ACL_NAME}} in
EOF
}

write_backups() {
  mkdir -p backups/wave2_cutover/switches backups/wave2_cutover/routers backups/pre_wave3 backups/wave_0_flat
  python3 - <<'PY'
from pathlib import Path
import yaml

root = Path(".")
inv = yaml.safe_load((root / "inventory/device_inventory.yaml").read_text(encoding="utf-8"))
canary = "dist-hq-dal-main-01"
scoped = [d for d in inv["devices"] if d.get("migration_state") in {"legacy", "partial"}]
by_name = {d["hostname"]: d for d in inv["devices"]}
anchor = by_name.get(canary)
if anchor and anchor.get("migration_state") == "segmented" and not any(d["hostname"] == canary for d in scoped):
    scoped.append(anchor)
hosts = sorted(d["hostname"] for d in scoped)
marker = "! apexora-pre-wave3-boundary snapshot — do not overwrite after migration edits"
(root / "inventory/wave3_validation_scope.yaml").write_text(
    yaml.dump(
        {
            "schema_version": "apexora-wave3-validation-scope-1",
            "wave_id": "wave_3",
            "host_count": len(hosts),
            "canary_anchor": canary,
            "source": "authoritative static list for Wave 3 ACL, wave, and rollback exports",
            "hostnames": hosts,
        },
        sort_keys=False,
    ),
    encoding="utf-8",
)

def config_path(hostname: str, role: str) -> Path | None:
    if role == "access":
        p = root / "switches/access" / hostname / "running.conf"
    elif role == "distribution":
        p = root / "switches/distribution" / hostname / "running.conf"
    elif role == "core":
        p = root / "switches/core" / hostname / "running.conf"
    else:
        p = next((p / "running.conf" for p in (root / "routers").rglob(hostname) if p.is_dir()), None)
    return p if p and p.is_file() else None

snap_dir = root / "backups/pre_wave3"
snap_dir.mkdir(parents=True, exist_ok=True)
for hostname in hosts:
    role = by_name[hostname]["role"]
    src = config_path(hostname, role)
    if src is None:
        continue
    body = src.read_text(encoding="utf-8")
    (snap_dir / f"{hostname}.conf.snapshot").write_text(f"{marker}\n{body}", encoding="utf-8")
PY
  cp switches/access/acc-emea-fra-lab-01/running.conf backups/wave2_cutover/switches/dist-apac-sin-main-01.conf.snapshot 2>/dev/null || true
  cp routers/campus-hq-dal/rtr-hq-dal-edge-01/running.conf backups/wave2_cutover/routers/rtr-emea-lon-edge-02.conf.snapshot 2>/dev/null || true
  cat > backups/wave_0_flat/FLAT-NETWORK-README.txt <<'EOF'
Flat Layer-2 network snapshots — DO NOT RESTORE for Wave 3 rollback.
Reference only for audit trail.
EOF
  cat > backups/wave_0_flat/acc-flat-era-01.conf.snapshot <<'EOF'
! Wave 0 flat network snapshot (read-only)
hostname acc-flat-era-01
interface Vlan110
 ip address 10.1.110.1 255.255.255.0
interface TenGigabitEthernet1/1/1
 switchport trunk allowed vlan all
EOF
}

write_configs_assembly() {
  mkdir -p configs/assembly configs/campuses configs/snippets
  cat > configs/assembly/source_precedence.yaml <<'EOF'
schema_version: apexora-assembly-1
consult_legacy_when_present: true
tiers:
  - vlans/catalog.yaml
  - vrfs/catalog.yaml
  - interfaces/gateway/gateway_bindings.yaml
  - interfaces/trunk/trunk_policy.yaml
  - acl/catalog.yaml
active_sections:
  - policy-source-precedence-2026
  - enterprise-network-standards-2026
  - campus-design-guide-2026
  - three-tier-campus-architecture-2026
  - vlan-assignment-standards-2026
  - vlan-identity
  - vlan-naming-standard-2026
  - vlan-campus-allocation-2026
  - vrf-policy-2026
  - vrf-rd-rt-numbering-2026
  - vrf-leak-exceptions-2026
  - vrf-gateway-tier-2026
  - interface-naming-standard-2026
  - device-hostname-standard-2026
  - port-description-standard-2026
  - acl-standards-2026
  - acl-object-group-usage-2026
  - acl-svi-binding-2026
  - trunk-policy
  - trunk-selective-allow-list-2026
  - trunk-native-vlan-2026
  - gateway-placement
  - hsrp-vrrp-standard-2026
  - qos-standards-2026
  - qos-campus-binding-2026
  - maintenance-procedures-2026
  - maintenance-window-wave3-2026
  - change-control-segmentfirst-2026
  - migration-runbook-wave3-2026
  - wave3-canary-gate
  - wave3-regional-order
  - migration-handbook-access-2026
  - migration-handbook-distribution-2026
  - migration-handbook-wan-edge-2026
  - rollback-snapshot-policy-2026
  - rollback-bundle-completeness
  - emergency-rollback-wave3-2026
  - post-validate-hook-2026
  - site-operations-hq-dal-2026
  - site-operations-amw-sea-2026
  - site-operations-emea-lon-2026
  - site-operations-emea-fra-2026
  - site-operations-apac-sin-2026
  - site-operations-apac-tyo-2026
  - role-runbook-access-2026
  - role-runbook-distribution-2026
  - role-runbook-core-2026
  - role-runbook-wan-edge-2026
  - vlan-troubleshooting-guide-2026
  - trunk-troubleshooting-guide-2026
  - gateway-troubleshooting-guide-2026
  - acl-troubleshooting-guide-2026
  - compliance-segmentation-2026
retired_vlan_families:
  - FLAT-USERS
  - FLAT-SERVERS
superseded_sections:
  - flat-trunk-all
  - access-layer-gateway
EOF
  for campus in "${CAMPUS_IDS[@]}"; do
    cat > "configs/campuses/${campus}_overlay.yaml" <<EOF
schema_version: apexora-campus-overlay-1
campus: ${campus}
segmentation_wave: wave_3
default_gateway_tier: distribution
EOF
  done
  cat > configs/snippets/selective_trunk.conf.fragment <<'EOF'
switchport trunk allowed vlan 2001-2180
switchport mode trunk
EOF
}

write_docs() {
  mkdir -p docs data services/hooks
  cat > docs/segmentation_contract.md <<'EOF'
# SegmentFirst documentation index

Pipeline export shapes, field requirements, and stage gates are defined under
`schemas/pipeline/` (`exports.yaml`, `stage_gates.yaml`). Regenerate artifacts
through `scripts/run-netsegctl.sh`.

Assembly authority and active policy section IDs live in
`configs/assembly/source_precedence.yaml`. Wave 3 validation scope is the
static 48-host list in `inventory/wave3_validation_scope.yaml`.
EOF

  cat > data/fleet_stats.json <<'EOF'
{"access_switches":52,"distribution_switches":14,"core_switches":6,"routers":24,"vlans":180,"vrfs":30}
EOF
  cat > data/evaluation_clock.json <<'EOF'
{"as_of":"2026-03-15T08:00:00Z","program":"segmentfirst-wave-3"}
EOF

  cat > services/hooks/post-validate.sh <<'EOF'
#!/usr/bin/env bash
# Active post-deploy validation hook
set -euo pipefail
host="${1:-unknown}"
echo "post-validate-ok ${host}"
EOF
  chmod +x services/hooks/post-validate.sh
}

write_mgmt_interfaces() {
  mkdir -p interfaces/management
  local m=1
  while [[ $m -le 40 ]]; do
    cat > "interfaces/management/MGMT-$(printf '%03d' "$m").conf" <<EOF
! Out-of-band management interface ${m}
interface GigabitEthernet0
 description OOB Management
 ip address 10.250.0.${m} 255.255.255.0
 vrf forwarding MGMT
EOF
    m=$((m + 1))
  done
}

write_routing_interfaces() {
  mkdir -p interfaces/routing
  local r=1
  while [[ $r -le 80 ]]; do
    cat > "interfaces/routing/RT-$(printf '%03d' "$r").conf" <<EOF
! L3 routing interface ${r}
interface GigabitEthernet0/0/$((r % 4))
 description WAN or core routed link
 ip vrf forwarding CORP-IT
 ip address 10.200.$((r / 256)).$((r % 256)) 255.255.255.252
 ip ospf 1 area 0
EOF
    r=$((r + 1))
  done
}

write_juniper_samples() {
  mkdir -p switches/access/acc-apac-sin-hub-01/juniper
  cat > switches/access/acc-apac-sin-hub-01/juniper/running.conf <<'EOF'
/* acc-apac-sin-hub-01 — Juniper EX4300 */
system {
    host-name acc-apac-sin-hub-01;
}
vlans {
    SEG-045 {
        vlan-id 2045;
    }
    LEGACY-FLAT-045 {
        vlan-id 145;
    }
}
interfaces {
    ge-0/0/0 {
        unit 0 {
            family ethernet-switching {
                interface-mode access;
                vlan {
                    members LEGACY-FLAT-045;
                }
            }
        }
    }
    xe-0/1/0 {
        unit 0 {
            family ethernet-switching {
                interface-mode trunk;
                vlan {
                    members [ SEG-045 SEG-046 ];
                }
            }
        }
    }
}
EOF
}

# ── Main ─────────────────────────────────────────────────────────────────────
write_vrf_catalog
write_vlan_catalog
write_acl_catalog
write_qos_catalog
write_interfaces_and_trunks
write_fleet
write_legacy
write_deployment
write_templates
write_backups
write_configs_assembly
write_docs
write_mgmt_interfaces
write_routing_interfaces
write_juniper_samples

echo "Generated Apexora SegmentFirst Wave 3 environment under ${ROOT}"
