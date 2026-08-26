#!/usr/bin/env bash
set -euo pipefail

# Restore lockout / bind / roster authority planes. Leave C sources alone.

log_line() { printf '[oracle] %s\n' "$1"; }

write_plane_a() {
  log_line "publish tip faillock authority plane"
  # Tip deny + active count pack + active carryover only (desk: data/corp/*).
  cat > /app/ctl/p_a.json <<'EOF'
{
  "schema": 1,
  "revision": "signed-tip-a",
  "deny": 3,
  "count_modules": ["common-auth", "pam_unix", "pam_otp", "pam_wheel"],
  "carryover": {
    "ian": 3,
    "bob": 0,
    "dave": 0,
    "henry": 0
  },
  "phantom_slugs": ["alice", "kate", "leo", "carol", "frank", "grace"],
  "exclude_modules": ["pam_sss", "pam_rootok"],
  "notes": ["tip_deny", "active_carry_only", "signed_count_pack", "phantoms_zero"]
}
EOF
}

write_plane_b() {
  log_line "publish tip bind authority plane"
  cat > /app/ctl/p_b.json <<'EOF'
{
  "schema": 1,
  "revision": "signed-tip-b",
  "reject_override": true,
  "force_map": {},
  "terminal_wins": true,
  "wiring_reminder": {
    "sshd": "sshd-stack",
    "sudo": "sudo-stack",
    "portal": "portal-stack",
    "su": "su-stack"
  },
  "notes": ["reject_bridge_aliases", "table_id_only"]
}
EOF
}

write_plane_c() {
  log_line "publish tip roster and realm plane"
  cat > /app/ctl/p_c.json <<'EOF'
{
  "schema": 1,
  "revision": "signed-tip-c",
  "realm_mode": "lower",
  "prefer_roster": true,
  "roster": {
    "alice@corp.example.com": 999999,
    "bob@corp.example.com": 999999,
    "carol@corp.example.com": 999999,
    "dave@corp.example.com": 999999,
    "eve@corp.example.com": 500,
    "frank@corp.example.com": 999999,
    "grace@corp.example.com": 999999,
    "henry@corp.example.com": 999999,
    "ian@corp.example.com": 999999,
    "kate@corp.example.com": 999999,
    "leo@corp.example.com": 999999
  },
  "notes": ["signed_expiry_tip", "realm_fold"]
}
EOF
}

write_runtime() {
  log_line "publish secure runtime defaults"
  cat > /app/rt/opts.json <<'EOF'
{
  "schema": 1,
  "revision": "secure-defaults",
  "bind_digest": true,
  "honor_legacy_overrides": false,
  "probe_implies_lockout": false,
  "require_ctl_planes": true,
  "reject_blanket_lockout": true,
  "reject_single_stack_papering": true,
  "audit_tag": "faillock-strict"
}
EOF
  cat > /app/rt/export_env.sh <<'EOF'
#!/usr/bin/env bash
# Runtime defaults exported before pack replay.
# shellcheck disable=SC2034
PAM_HONOR_OVERRIDE="${PAM_HONOR_OVERRIDE:-0}"
PAM_PROBE_IMPLIES_LOCK="${PAM_PROBE_IMPLIES_LOCK:-0}"
PAM_REALM_FOLD="${PAM_REALM_FOLD:-lower}"
PAM_BIND_DIGEST="${PAM_BIND_DIGEST:-1}"
EOF
  chmod 0755 /app/rt/export_env.sh
}

write_ledger() {
  local slug="$1"
  local failures="$2"
  local last_fail="$3"
  local source="$4"
  cat > "/app/var/tally/${slug}.tally" <<EOF
failures=${failures}
last_fail=${last_fail}
source=${source}
shift=night-cutover
EOF
}

reconcile_durable_tallies() {
  log_line "mirror active carry rows and clear phantom bridge tallies"
  mkdir -p /app/var/tally
  write_ledger ian 3 5999 desk-tip
  write_ledger bob 0 0 desk-tip
  write_ledger dave 0 0 desk-tip
  write_ledger henry 0 0 desk-tip
  write_ledger alice 0 0 phantom-clear
  write_ledger kate 0 0 phantom-clear
  write_ledger leo 0 0 phantom-clear
  write_ledger carol 0 0 phantom-clear
  write_ledger frank 0 0 phantom-clear
  write_ledger grace 0 0 phantom-clear
}

retire_legacy_hijack() {
  log_line "retire legacy override fragment so reject_override governs"
  rm -f /app/config/k2_bindings.toml
}

cross_check_desk() {
  log_line "cross-check published planes against corp desk tips"
  python3 - <<'PY'
import json
import sys
from pathlib import Path

corp = Path("/app/data/corp")
deny = next(
    int(link["deny"])
    for link in json.loads((corp / "deny_chain.json").read_text(encoding="utf-8"))["links"]
    if link.get("tip")
)
mods = next(
    c["modules"]
    for c in json.loads((corp / "module_desk.json").read_text(encoding="utf-8"))["candidates"]
    if c.get("active")
)
carry = {
    row["slug"]: int(row["failures"])
    for row in json.loads((corp / "carry_desk.json").read_text(encoding="utf-8"))["rows"]
    if row.get("active")
}
roster = {
    row["actor"]: int(row["expiry"])
    for row in json.loads((corp / "roster_desk.json").read_text(encoding="utf-8"))["principals"]
    if row.get("tip")
}
realm = json.loads((corp / "roster_desk.json").read_text(encoding="utf-8"))["realm_mode_tip"]
bind = json.loads((corp / "bind_desk.json").read_text(encoding="utf-8"))

a = json.loads(Path("/app/ctl/p_a.json").read_text(encoding="utf-8"))
b = json.loads(Path("/app/ctl/p_b.json").read_text(encoding="utf-8"))
c = json.loads(Path("/app/ctl/p_c.json").read_text(encoding="utf-8"))
opts = json.loads(Path("/app/rt/opts.json").read_text(encoding="utf-8"))

if int(a["deny"]) != deny:
    sys.exit(f"oracle: deny {a['deny']} != tip {deny}")
if list(a["count_modules"]) != list(mods):
    sys.exit("oracle: count_modules mismatch tip pack")
if {k: int(v) for k, v in a["carryover"].items()} != carry:
    sys.exit("oracle: carryover mismatch active desk rows")
if b.get("reject_override") is not True or b.get("force_map"):
    sys.exit("oracle: bind plane still carries bridge aliases")
if c.get("realm_mode") != realm:
    sys.exit("oracle: realm_mode mismatch")
for actor, expiry in roster.items():
    if int(c["roster"][actor]) != expiry:
        sys.exit(f"oracle: roster {actor} mismatch")
if not opts.get("bind_digest") or opts.get("honor_legacy_overrides") or opts.get("probe_implies_lockout"):
    sys.exit("oracle: runtime defaults not strict")
if not bind.get("reject_override_tip"):
    sys.exit("oracle: bind desk tip inconsistent")
if Path("/app/config/k2_bindings.toml").exists():
    sys.exit("oracle: legacy hijack still present")
print("oracle desk cross-check ok")
PY
}

rebuild_and_replay() {
  log_line "rebuild and publish pam_lockout_report.json"
  bash /app/scripts/build.sh
  bash /app/scripts/stack_probe.sh >/dev/null || true
  rm -f /app/output/pam_lockout_report.json
  # shellcheck disable=SC1091
  source /app/rt/export_env.sh
  python3 /app/tools/auth_tape_replay
  test -s /app/output/pam_lockout_report.json
  python3 - <<'PY'
import json
import sys
from pathlib import Path

report = json.loads(Path("/app/output/pam_lockout_report.json").read_text(encoding="utf-8"))
summary = report.get("summary", {})
if not summary.get("pack_ok"):
    sys.exit("oracle: pack_ok false after authority restore")
by_id = {r["conversation_id"]: r for r in report["audits"]}
checks = {
    "su_bind": ("stack_binding", "su-stack"),
    "ssh_bind": ("stack_binding", "sshd-stack"),
    "sss_noise": ("lockout_active", False),
    "deny_edge": ("lockout_active", True),
    "expiry_edge": ("expired_account", True),
    "clean_pass": ("lockout_active", False),
}
for tape, (field, want) in checks.items():
    got = by_id[tape][field]
    if got != want:
        sys.exit(f"oracle: {tape}.{field}={got!r} want {want!r}")
if summary.get("total_lockouts", 0) < 3:
    sys.exit("oracle: expected multiple lockouts")
print("oracle report ok")
PY
}

write_plane_a
write_plane_b
write_plane_c
write_runtime
reconcile_durable_tallies
retire_legacy_hijack
cross_check_desk
rebuild_and_replay
