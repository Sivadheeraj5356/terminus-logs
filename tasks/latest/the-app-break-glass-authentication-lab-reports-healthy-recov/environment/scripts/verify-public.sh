#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="${APP_ROOT:-/app}"
AUTHCTL="$APP_ROOT/bin/authctl"
LAB_ROOT="$APP_ROOT/work/public"
REPORT_DIR="$APP_ROOT/reports"

expect_deny() {
    if "$AUTHCTL" login "$@" >/dev/null 2>&1; then
        echo "expected login denial: $*" >&2
        return 1
    fi
}

assert_line() {
    local text="$1"
    local expected="$2"
    if ! grep -Fqx -- "$expected" <<<"$text"; then
        echo "missing snapshot line: $expected" >&2
        printf '%s\n' "$text" >&2
        return 1
    fi
}

"$APP_ROOT/scripts/build.sh" >/dev/null
"$APP_ROOT/scripts/regenerate-policy.sh" >/dev/null
"$APP_ROOT/scripts/new-lab.sh" "$LAB_ROOT" >/dev/null

"$AUTHCTL" probe-recovery --root "$LAB_ROOT" --user alice --secret main-token >/dev/null
"$AUTHCTL" probe-recovery --root "$LAB_ROOT" --user carol --secret carol-token >/dev/null

"$AUTHCTL" login --root "$LAB_ROOT" --user bob --method password --secret battery-staple --session bob-normal >/dev/null
"$AUTHCTL" logout --root "$LAB_ROOT" --session bob-normal >/dev/null

for attempt in 1 2 3; do
    expect_deny --root "$LAB_ROOT" --user alice --method password --secret "wrong-$attempt" --session "bad-$attempt"
done
expect_deny --root "$LAB_ROOT" --user alice --method password --secret correct-horse --session locked-password

"$AUTHCTL" login --root "$LAB_ROOT" --user bob --method password --secret battery-staple --session occupied >/dev/null
expect_deny --root "$LAB_ROOT" --user alice --method recovery --secret collide-token --session occupied
collision_snapshot="$("$AUTHCTL" snapshot --root "$LAB_ROOT" --user alice)"
assert_line "$collision_snapshot" "locked=true"
assert_line "$collision_snapshot" "token.A-COLLIDE=fresh"
"$AUTHCTL" logout --root "$LAB_ROOT" --session occupied >/dev/null

"$AUTHCTL" login --root "$LAB_ROOT" --user alice --method recovery --secret main-token --session alice-r1 >/dev/null
"$AUTHCTL" logout --root "$LAB_ROOT" --session alice-r1 >/dev/null
expect_deny --root "$LAB_ROOT" --user alice --method recovery --secret main-token --session alice-replay

# Delegated password ignore path: same recovery obligations as auth_err.
for attempt in 1 2 3; do
    expect_deny --root "$LAB_ROOT" --user carol --method password --secret "carol-wrong-$attempt" --session "carol-bad-$attempt"
done
expect_deny --root "$LAB_ROOT" --user carol --method password --secret delegated-pass --session carol-locked
"$AUTHCTL" login --root "$LAB_ROOT" --user carol --method recovery --secret carol-token --session carol-r1 >/dev/null
"$AUTHCTL" logout --root "$LAB_ROOT" --session carol-r1 >/dev/null
expect_deny --root "$LAB_ROOT" --user carol --method recovery --secret carol-token --session carol-replay

before="$("$AUTHCTL" snapshot --root "$LAB_ROOT" --user alice)"
assert_line "$before" "failures=0"
assert_line "$before" "locked=false"
assert_line "$before" "token.A-COLLIDE=fresh"
assert_line "$before" "token.A-MAIN=consumed"
assert_line "$before" "session.alice-r1=closed:recovery"
assert_line "$before" "audit.login=1"
assert_line "$before" "audit.logout=1"
assert_line "$before" "audit.denied=6"

carol_before="$("$AUTHCTL" snapshot --root "$LAB_ROOT" --user carol)"
assert_line "$carol_before" "failures=0"
assert_line "$carol_before" "locked=false"
assert_line "$carol_before" "token.C-MAIN=consumed"
assert_line "$carol_before" "session.carol-r1=closed:recovery"
assert_line "$carol_before" "audit.login=1"
assert_line "$carol_before" "audit.logout=1"
assert_line "$carol_before" "audit.denied=5"

"$AUTHCTL" rebuild --root "$LAB_ROOT" >/dev/null
after="$("$AUTHCTL" snapshot --root "$LAB_ROOT" --user alice)"
if [[ "$before" != "$after" ]]; then
    echo "live and rebuilt state diverged" >&2
    diff -u <(printf '%s\n' "$before") <(printf '%s\n' "$after") >&2 || true
    exit 1
fi
carol_after="$("$AUTHCTL" snapshot --root "$LAB_ROOT" --user carol)"
if [[ "$carol_before" != "$carol_after" ]]; then
    echo "carol live and rebuilt state diverged" >&2
    diff -u <(printf '%s\n' "$carol_before") <(printf '%s\n' "$carol_after") >&2 || true
    exit 1
fi

mkdir -p "$REPORT_DIR"
source_hash="$(sha256sum "$APP_ROOT/policy/login.policy" | awk '{print $1}')"
runtime_hash="$(sha256sum "$APP_ROOT/runtime/pam.d/login.conf" | awk '{print $1}')"
cat > "$REPORT_DIR/recovery-proof.json" <<JSON
{
  "task": "pam-stack-recovery-token-order",
  "policy_source_sha256": "$source_hash",
  "policy_runtime_sha256": "$runtime_hash",
  "cycle": ["failed-passwords", "recovery", "logout", "replay", "ignore-recovery", "rebuild"],
  "user": "alice",
  "failures": 0,
  "locked": false,
  "main_token": "consumed",
  "collision_token": "fresh",
  "session": "closed",
  "audit": {"login": 1, "logout": 1, "denied": 6},
  "ignore_user": "carol",
  "ignore_main_token": "consumed",
  "state_converged": true
}
JSON
printf 'public verification passed\n'
