#!/bin/bash
set -euo pipefail
# Oracle reference for harden-java-compose-release-gates.
# Overwrites the five stub modules with the reference implementation, fixes
# the planted ComposeLoader override-file defect, rebuilds gate.jar, brings
# up the service, smoke-tests /health and one /gate/evaluate call, then
# stops the service so the harness starts from a clean slot.

APP=/app
ORACLE_SRC="${ORACLE_SRC_DIR:-/oracle/oracle_src}"
if [[ ! -d "$ORACLE_SRC" ]]; then
    ORACLE_SRC="$(cd "$(dirname "$0")" && pwd)/oracle_src"
fi

cd "$APP"

# 1) Fixtures: rebuild the deterministic repo fixture so re-runs are safe.
bash /app/scripts/build_repo_fixture.sh >/dev/null

# 2) Install the correct implementations for the five stub modules and the
#    ComposeLoader merge fix.
install -m 0644 "$ORACLE_SRC/ComposeLoader.java"    src/ComposeLoader.java
install -m 0644 "$ORACLE_SRC/PolicyEngine.java"     src/PolicyEngine.java
install -m 0644 "$ORACLE_SRC/TagEvidence.java"      src/TagEvidence.java
install -m 0644 "$ORACLE_SRC/ExceptionWindows.java" src/ExceptionWindows.java
install -m 0644 "$ORACLE_SRC/HookCheck.java"        src/HookCheck.java
install -m 0644 "$ORACLE_SRC/Decision.java"         src/Decision.java

# 3) Rebuild the jar and reseed the H2 DB (build.sh does both).
/app/build.sh >/dev/null

# 4) Stop any previous service instance, then start fresh.
if [ -f /app/gate.pid ]; then
    pid=$(cat /app/gate.pid || echo)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
    fi
    rm -f /app/gate.pid
fi

bash /app/scripts/run_gate.sh

# 5) Smoke-check /health.
health=$(curl -sSf http://127.0.0.1:8971/health)
if [ "$health" != '{"status":"ok"}' ]; then
    echo "ORACLE_FAIL: /health returned: $health" >&2
    exit 1
fi

# 6) Visible fixture at evaluationTime=2026-06-15Z. Expected: deny with
#    exactly one reason, CDSS-SVC-012 on service `cache`. This is the (v)
#    outcome; any additional reason or a deny on any other subject means
#    the base fixture is over-specified (states (i)-(iv) should each
#    approve on partial implementations — a deny on any other subject
#    would be visible here as an extra reason and points at a mis-seed).
REQ='{"repo":"/app/repos/payments-stack","tag":"release/v2.1.0","evaluationTime":"2026-06-15T12:00:00Z"}'
resp=$(curl -sSf -X POST -H "Content-Type: application/json" -d "$REQ" \
    http://127.0.0.1:8971/gate/evaluate)

python3 - <<PY "$resp"
import json, sys
r = json.loads(sys.argv[1])
assert r["decision"] == "deny", f"SENTINEL FAIL: state (v) must deny, got {r}"
assert len(r["reasons"]) == 1, \
    f"SENTINEL FAIL: (v) must have exactly one reason (extras mean a base-fixture " \
    f"attribute is over-specified and one of states (i)-(iv) already denies), got {r}"
only = r["reasons"][0]
assert only["code"] == "CDSS-SVC-012" and only["service"] == "cache", \
    f"SENTINEL FAIL: (v) reason must be CDSS-SVC-012 on cache — anything else " \
    f"means the fixture triggers a non-A7 violation. Got {only}"
print("ORACLE self-check passed (state v):", only)
PY

# 6b) Mutate the waiver's approved_at to AFTER Amendment 7's effective_date
#     and verify the same request now approves. This proves the temporal-
#     binding predicate is load-bearing on this fixture: if state (iv) is
#     the only thing driving the deny, moving approved_at forward should
#     not change the decision. Reseeds the DB back to the on-disk seed
#     after the check so the container is left in its shipped state.
cat >/tmp/mutate_waiver.sql <<'SQL'
UPDATE exception_windows SET approved_at = TIMESTAMP '2026-06-01 00:00:00' WHERE id = 1;
SQL
java -cp /opt/jars/h2.jar org.h2.tools.RunScript \
    -url "jdbc:h2:file:/app/data/approvals;IFEXISTS=TRUE" \
    -user sa -script /tmp/mutate_waiver.sql >/dev/null

resp2=$(curl -sSf -X POST -H "Content-Type: application/json" -d "$REQ" \
    http://127.0.0.1:8971/gate/evaluate)

python3 - <<PY "$resp2"
import json, sys
r = json.loads(sys.argv[1])
assert r["decision"] == "approve", \
    f"BINDING SENTINEL FAIL: with waiver.approved_at >= A7.effective_date the " \
    f"waiver must suspend the amended obligation and the visible fixture must " \
    f"approve. Got {r} — this means the reference impl is not gating on the " \
    f"temporal-binding predicate, or the fixture has an extra violation."
print("ORACLE binding-predicate check passed (mutated waiver → approve)")
PY

# Restore the original approved_at so re-runs from the fresh image work,
# and so any test harness that observes the DB sees the shipped seed.
cat >/tmp/restore_waiver.sql <<'SQL'
UPDATE exception_windows SET approved_at = TIMESTAMP '2026-03-15 00:00:00' WHERE id = 1;
SQL
java -cp /opt/jars/h2.jar org.h2.tools.RunScript \
    -url "jdbc:h2:file:/app/data/approvals;IFEXISTS=TRUE" \
    -user sa -script /tmp/restore_waiver.sql >/dev/null
rm -f /tmp/mutate_waiver.sql /tmp/restore_waiver.sql

# 7) Stop the service so the runner starts from a known-clean slot.
if [ -f /app/gate.pid ]; then
    pid=$(cat /app/gate.pid || echo)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        # Give the process a moment to unbind the port cleanly.
        for _ in 1 2 3 4 5; do
            if kill -0 "$pid" 2>/dev/null; then sleep 0.2; else break; fi
        done
        kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f /app/gate.pid
fi

echo "ORACLE_DONE"
