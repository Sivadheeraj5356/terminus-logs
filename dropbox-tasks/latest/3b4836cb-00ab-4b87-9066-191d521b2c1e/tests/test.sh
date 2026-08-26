#!/bin/bash
# Harbor verifier — deps in environment/Dockerfile only.
# All verifier staging runs after the agent phase (this script).
set -uo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
printf '%s\n' '{"version":"1.0.0","results":{"summary":{"tests":0,"passed":0,"failed":0,"pending":0,"skipped":0,"other":0}}}' > /logs/verifier/ctrf.json

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set."
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

cd /app || {
    echo 0 > /logs/verifier/reward.txt
    exit 1
}

TEST_DIR="${TEST_DIR:-/tests}"

if [ ! -x /opt/verifier-venv/bin/python ]; then
    echo "Error: trusted verifier python missing."
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

# Restore trusted toolchain from root-owned image copies (agent cannot mutate them).
mkdir -p /opt/verifier-bin /opt/verifier-scripts
for name in go runuser; do
    src="/opt/verifier-image/${name}"
    dest="/opt/verifier-bin/${name}"
    if [ ! -x "${src}" ]; then
        echo "Error: trusted ${name} missing from image."
        echo 0 > /logs/verifier/reward.txt
        exit 1
    fi
    cp -af "${src}" "${dest}"
    chown root:root "${dest}"
    chmod 0555 "${dest}"
done

# Restore grading wrappers from /tests mount only (not available during agent phase).
if [ ! -f "${TEST_DIR}/rebuild-rebooking.sh" ]; then
    echo "Error: missing rebuild-rebooking.sh on tests mount."
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi
cp "${TEST_DIR}/rebuild-rebooking.sh" /opt/verifier-scripts/rebuild-rebooking
sed -i 's/\r$//' /opt/verifier-scripts/rebuild-rebooking
chown root:root /opt/verifier-scripts/rebuild-rebooking
chmod 0555 /opt/verifier-scripts/rebuild-rebooking

if [ ! -f "${TEST_DIR}/run-as-rebooker.sh" ]; then
    echo "Error: missing run-as-rebooker.sh on tests mount."
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi
cp "${TEST_DIR}/run-as-rebooker.sh" /opt/verifier-scripts/run-as-rebooker
sed -i 's/\r$//' /opt/verifier-scripts/run-as-rebooker
chown root:root /opt/verifier-scripts/run-as-rebooker
chmod 0555 /opt/verifier-scripts/run-as-rebooker

# Remove any agent-planted decoy under /app.
rm -f /app/scripts/verifier-rebuild.sh /app/scripts/rebuild-rebooking
rm -f /app/pytest.py /app/pytest.pyc /app/rebooking_reference.py /app/rebooking_reference.pyc
rm -rf /app/pytest /app/__pycache__ /app/rebooking_reference 2>/dev/null || true

rm -rf /opt/verifier-lib /opt/verifier-fixtures /opt/verifier-run
mkdir -p /opt/verifier-lib /opt/verifier-fixtures /opt/verifier-run
if [ -f "${TEST_DIR}/rebooking_reference.py" ]; then
    cp "${TEST_DIR}/rebooking_reference.py" /opt/verifier-lib/rebooking_reference.py
    /opt/verifier-venv/bin/python -m compileall -q -b /opt/verifier-lib
    rm -f /opt/verifier-lib/rebooking_reference.py
fi
for d in competing-seats connection alliance manifest-order tiebreak fare-rules partial-legs conn-cancel-next partner-ok upgrade-ok upgrade-off fare-class-tiebreak; do
    if [ -d "${TEST_DIR}/verifier-fixtures/hidden-${d}" ]; then
        cp -a "${TEST_DIR}/verifier-fixtures/hidden-${d}" "/opt/verifier-fixtures/rebook-hidden-${d}"
    fi
done
chown -R root:root /opt/verifier-lib /opt/verifier-fixtures /opt/verifier-scripts /opt/verifier-run /opt/verifier-bin /opt/verifier-venv
chmod 700 /opt/verifier-lib /opt/verifier-fixtures
chmod 755 /opt/verifier-bin /opt/verifier-run
chmod -R u+rwX,go-rwx /opt/verifier-lib /opt/verifier-fixtures 2>/dev/null || true
chmod -R a+rX,go-w /opt/verifier-venv 2>/dev/null || true

# Lock the mounted /tests tree so the candidate user cannot read reference or fixtures.
if [ -d "${TEST_DIR}" ]; then
    chown -R root:root "${TEST_DIR}" 2>/dev/null || true
    chmod 700 "${TEST_DIR}" 2>/dev/null || true
    chmod -R u+rwX,go-rwx "${TEST_DIR}" 2>/dev/null || true
fi

chown -R rebooker:rebooker /app/data /app/state /app/output /app/bin 2>/dev/null || true
mkdir -p /app/state /app/output /app/bin
chown -R rebooker:rebooker /app/data /app/state /app/output /app/bin 2>/dev/null || true

# Trusted verifier entrypoint: image venv python, root-only cwd, PYTHONPATH without /app.
cd /opt/verifier-run || {
    echo 0 > /logs/verifier/reward.txt
    exit 1
}
export PATH="/opt/verifier-venv/bin:/opt/verifier-bin:/opt/verifier-scripts:${PATH}"
export PYTHONPATH="/opt/verifier-lib"
export PYTHONSAFEPATH=1
unset PYTHONHOME

set +e
python3 -m pytest -rA -o cache_dir=/tmp/pytest_cache --rootdir /opt/verifier-run --ctrf /logs/verifier/ctrf.json "${TEST_DIR}/test_outputs.py"
if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
