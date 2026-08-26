#!/bin/bash
set -euo pipefail

APP="${APP_DIR:-/app}"
SRC="$APP/src"
ADDR="127.0.0.1:8849"
AUDIT="/tmp/keystone_oracle_audit.log"
PROBE="/tmp/keystone_probe.py"

fix_file() {
  grep -Frl "$1" "$SRC" | head -1
}

cat > "$PROBE" <<'PYEOF'
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE = "http://127.0.0.1:8849"
AUDIT = "/tmp/keystone_oracle_audit.log"
S = uuid.uuid4().hex[:8]


def call(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("content-type", "application/json")
    if token:
        req.add_header("authorization", "Bearer " + token)
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        raw = resp.read()
        return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as err:
        raw = err.read()
        try:
            parsed = json.loads(raw) if raw else {}
        except ValueError:
            parsed = {}
        return err.code, parsed


def login(user, password):
    status, body = call("POST", "/v1/auth/token", body={"username": user, "password": password})
    assert status == 200, f"login {user}: {status} {body}"
    return body["token"], body["account_id"]


def new_validator(token, attested=True):
    status, body = call(
        "POST", "/v1/validators", token,
        {"name": f"v-{S}-{uuid.uuid4().hex[:6]}", "stake": 2, "attested": attested},
    )
    assert status == 201, f"validator: {status} {body}"
    return body["id"]


def observe():
    erin, _ = login("erin", "erin-pw-6m4")
    alice, alice_id = login("alice", "alice-pw-9f3")
    carol, carol_id = login("carol", "carol-pw-7c2")
    dave, dave_id = login("dave", "dave-pw-2k9")
    bob, _ = login("bob", "bob-pw-4a1")
    _, st = call("GET", "/v1/relayer/status", erin)
    depth = st["finality_depth"]
    v = {}

    _, dep = call("POST", "/v1/relayer/deposits", erin,
                  {"l1_height": 700000, "recipient_account_id": alice_id, "amount": 6})
    call("POST", "/v1/relayer/reconcile", erin, {"l1_tip": 700000 + depth})
    _, after = call("GET", f"/v1/relayer/deposits/{dep['id']}", erin)
    v["deposit_withheld_at_depth"] = after.get("status") != "applied"

    _, before = call("GET", "/v1/account", carol)
    before_bal = before.get("l2_balance", 0)
    call("POST", "/v1/relayer/deposits", erin,
         {"l1_height": 700100, "recipient_account_id": carol_id, "amount": 9})
    call("POST", "/v1/relayer/reconcile", erin, {"l1_tip": 700100 + depth})
    _, credited = call("GET", "/v1/account", carol)
    v["settlement_credits_operator"] = (credited.get("l2_balance", 0) - before_bal) != 9

    call("POST", "/v1/relayer/deposits", erin,
         {"l1_height": 700200, "recipient_account_id": dave_id, "amount": 4})
    call("POST", "/v1/relayer/reconcile", erin, {"l1_tip": 700200 + depth})
    time.sleep(0.2)
    raw = open(AUDIT).read() if os.path.exists(AUDIT) else ""
    v["settlement_credential_persisted"] = '"settlement_credential"' in raw

    rid = call("POST", "/v1/referenda", alice, {"title": f"r-{S}", "visibility": "private"})[1]["id"]
    call("POST", f"/v1/referenda/{rid}/grants", alice, {"subject_account_id": carol_id, "may_delegate": True})
    call("POST", f"/v1/referenda/{rid}/delegations", carol, {"subject_account_id": dave_id})
    call("POST", f"/v1/referenda/{rid}/votes", dave, {"choice": "aye"})
    call("DELETE", f"/v1/referenda/{rid}/grants/{carol_id}", alice)
    status, _ = call("POST", f"/v1/referenda/{rid}/votes", dave, {"choice": "aye"})
    v["delegation_survives_revoke"] = status == 201

    status, _ = call("GET", "/v1/monitoring/stats", dave)
    v["monitoring_open_to_participant"] = status == 200

    au, _ = call("POST", "/v1/auth/token", body={"username": f"ghost-{S}", "password": "x"})
    ap, _ = call("POST", "/v1/auth/token", body={"username": "alice", "password": "wrong"})
    v["login_discloses_validity"] = au != ap

    uv = new_validator(alice, attested=False)
    status, _ = call("POST", f"/v1/validators/{uv}/activate", alice, {})
    v["unattested_validator_trusted"] = status == 200

    xv = new_validator(alice, attested=True)
    status, _ = call("GET", f"/v1/validators/{xv}", bob)
    v["cross_network_validator"] = status == 200

    return v


LABELS = {
    "deposit_withheld_at_depth": "a deposit that has reached the finality depth is withheld from L2",
    "settlement_credits_operator": "an applied deposit credits the relaying operator, not the recipient",
    "settlement_credential_persisted": "the settlement credential is persisted to the audit log",
    "delegation_survives_revoke": "a delegated vote survives its delegator losing the referendum",
    "monitoring_open_to_participant": "a plain participant reads operational statistics",
    "login_discloses_validity": "login discloses whether an account exists",
    "unattested_validator_trusted": "a validator with no attestation is activated",
    "cross_network_validator": "a validator is disclosed to an account in another network",
}

mode = sys.argv[1]
found = observe()
for key in LABELS:
    print(f"  [{'VIOLATED' if found.get(key) else 'enforced'}] {LABELS[key]}")
still = [k for k in LABELS if found.get(k)]
if mode == "verify" and still:
    print("INVARIANTS STILL VIOLATED:", still)
    sys.exit(1)
PYEOF

build() {
  ( cd "$APP" && cargo build --release --locked ) >/tmp/keystone_build.log 2>&1 \
    || { echo "build failed"; tail -20 /tmp/keystone_build.log; exit 1; }
}

launch() {
  pkill -x keystone 2>/dev/null || true
  sleep 0.3
  rm -f "$AUDIT"
  KEYSTONE_ADDR="$ADDR" KEYSTONE_AUDIT_PATH="$AUDIT" "$APP/target/release/keystone" &
  SRV=$!
  for _ in $(seq 1 60); do
    if curl -sf "http://$ADDR/v1/health" >/dev/null 2>&1; then break; fi
    sleep 0.5
  done
}

stop() {
  kill "$SRV" 2>/dev/null || true
  wait "$SRV" 2>/dev/null || true
}

echo "== observing the shipped node =="
build
launch
python3 "$PROBE" observe || true
stop

echo "== applying the fix for each observed violation =="

# A bridged deposit is applied as soon as it reaches the finality depth: the finalized frontier is the
# tip minus the depth, not one L1 block lower.
F="$(fix_file 'pub fn finalized_height')"
python3 - "$F" <<'PYEOF'
import sys
path = sys.argv[1]
src = open(path).read()
if "finality_depth + 1" not in src:
    print("finalized frontier already fixed")
else:
    src = src.replace(
        "l1_tip.saturating_sub(finality_depth + 1)",
        "l1_tip.saturating_sub(finality_depth)",
    )
    open(path, "w").write(src)
    print("finalized frontier fixed:", path)
PYEOF

# An applied deposit credits the account named as its recipient, not the operator that relayed it.
F="$(fix_file 'pub fn resolve(deposit: &Deposit)')"
python3 - "$F" <<'PYEOF'
import sys
path = sys.argv[1]
src = open(path).read()
if "deposit.owner_id.clone()" not in src:
    print("beneficiary already fixed")
else:
    src = src.replace("deposit.owner_id.clone()", "deposit.recipient_account_id.clone()")
    open(path, "w").write(src)
    print("beneficiary fixed:", path)
PYEOF

# The one-time settlement credential is stripped before a settlement record reaches disk.
F="$(fix_file 'STORAGE_DENYLIST')"
python3 - "$F" <<'PYEOF'
import sys
path = sys.argv[1]
src = open(path).read()
if "settlement_credential" in src:
    print("audit storage denylist already fixed")
else:
    old = (
        'const STORAGE_DENYLIST: [&str; 7] = [\n'
        '    "password",\n'
        '    "token",\n'
        '    "secret",\n'
        '    "authorization",\n'
        '    "api_token",\n'
        '    "session_credential",\n'
        '    "signing_key",\n'
        '];'
    )
    assert old in src, "STORAGE_DENYLIST body not found"
    src = src.replace(
        old,
        'const STORAGE_DENYLIST: [&str; 8] = [\n'
        '    "password",\n'
        '    "token",\n'
        '    "secret",\n'
        '    "authorization",\n'
        '    "api_token",\n'
        '    "session_credential",\n'
        '    "settlement_credential",\n'
        '    "signing_key",\n'
        '];',
    )
    open(path, "w").write(src)
    print("audit storage denylist fixed:", path)
PYEOF

# A delegated ballot is effective only while the account that issued it still holds the referendum.
F="$(fix_file 'pub fn holds_delegated')"
python3 - "$F" <<'PYEOF'
import sys
path = sys.argv[1]
src = open(path).read()
if "seat_authority::holds" in src:
    print("delegation lapse already fixed")
else:
    src = src.replace(
        "use crate::store::state::AppState;",
        "use crate::governance::seat_authority;\nuse crate::store::state::AppState;",
        1,
    )
    old = "    delegation.is_some()\n}"
    assert old in src, "delegation_resolver body not found"
    src = src.replace(
        old,
        "    match delegation {\n"
        "        Some(grant) => seat_authority::holds(state, &grant.delegated_by, referendum),\n"
        "        None => false,\n"
        "    }\n}",
    )
    open(path, "w").write(src)
    print("delegation lapse fixed:", path)
PYEOF

# Operational statistics are restricted to the operator or admin role.
F="$(fix_file 'pub fn require_view')"
python3 - "$F" <<'PYEOF'
import sys
path = sys.argv[1]
src = open(path).read()
old = (
    "    if role_registry::permits(ctx.role, Permission::MonitoringView)\n"
    "        || role_registry::permits(ctx.role, Permission::BlockView)\n"
    "    {\n"
)
if old not in src:
    print("monitoring authorization already fixed")
else:
    src = src.replace(old, "    if role_registry::permits(ctx.role, Permission::MonitoringView) {\n")
    open(path, "w").write(src)
    print("monitoring authorization fixed:", path)
PYEOF

# A failed login must not disclose whether the account exists.
F="$(fix_file 'pub fn login(accounts: &AccountStore')"
python3 - "$F" <<'PYEOF'
import sys
path = sys.argv[1]
src = open(path).read()
old = (
    "        None => {\n"
    "            return Err(ApiError::new(\n"
    "                404,\n"
    '                "unknown_account",\n'
    '                "no account matches that username",\n'
    "            ))\n"
    "        }\n"
)
if old not in src:
    print("login disclosure already fixed")
else:
    src = src.replace(old, "        None => return Err(ApiError::unauthorized()),\n")
    open(path, "w").write(src)
    print("login disclosure fixed:", path)
PYEOF

# A validator with no integrity attestation is refused activation rather than trusted.
F="$(fix_file 'validator.attestation.is_empty()')"
python3 - "$F" <<'PYEOF'
import sys
path = sys.argv[1]
src = open(path).read()
old = "    if validator.attestation.is_empty() {\n        return Ok(());\n    }"
if old not in src:
    print("validator integrity check already fixed")
else:
    src = src.replace(
        old,
        "    if validator.attestation.is_empty() {\n"
        "        return Err(ApiError::unprocessable(\n"
        '            "validator_unattested",\n'
        '            "validator carries no integrity attestation",\n'
        "        ));\n"
        "    }",
    )
    open(path, "w").write(src)
    print("validator integrity check fixed:", path)
PYEOF

# Validator detail access is scoped to the owning network.
F="$(fix_file 'pub fn authorize(ctx: &AuthContext, validator: &Validator)')"
python3 - "$F" <<'PYEOF'
import sys
path = sys.argv[1]
src = open(path).read()
old = (
    "pub fn authorize(ctx: &AuthContext, validator: &Validator) -> Result<(), ApiError> {\n"
    "    if validator.owner_id == ctx.account_id {"
)
if old not in src:
    print("validator network scoping already fixed")
else:
    src = src.replace(
        old,
        "pub fn authorize(ctx: &AuthContext, validator: &Validator) -> Result<(), ApiError> {\n"
        "    if validator.network_id != ctx.network_id {\n"
        "        return Err(ApiError::forbidden());\n"
        "    }\n"
        "    if validator.owner_id == ctx.account_id {",
    )
    open(path, "w").write(src)
    print("validator network scoping fixed:", path)
PYEOF

echo "== rebuilding and re-probing the fixed node =="
build
launch
if python3 "$PROBE" verify; then
    verify_ok=1
else
    verify_ok=0
fi
stop

if [ "$verify_ok" -ne 1 ]; then
    echo "oracle failed: one or more invariants are still violated after the fixes"
    exit 1
fi
echo "oracle solution applied and verified"
