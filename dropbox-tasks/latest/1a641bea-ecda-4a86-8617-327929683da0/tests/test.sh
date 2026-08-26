#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

# Lock the answer files here, before any Python code is imported. The session
# fixture locks them again, but that runs inside pytest and so would be too late
# if an importable module had already been shadowed.
for f in /tests/vectors.json /tests/examples.json; do
    [ -e "$f" ] || continue
    chown 0:0 "$f" 2>/dev/null || true
    chmod 600 "$f" 2>/dev/null || true
done

# Run the suite from an isolated root-owned directory rather than the candidate's
# working directory, so no file the candidate controls can shadow pytest or any
# module it imports. This is what keeps sys.path[0] out of the candidate's reach.
RUNDIR=/run/verifier
rm -rf "$RUNDIR"
mkdir -p "$RUNDIR"
chmod 700 "$RUNDIR"
cd "$RUNDIR" || { echo 0 > /logs/verifier/reward.txt; exit 0; }

# Belt and braces on interpreters that support it (Python 3.11+): also refuse to
# put the working directory on sys.path at all. Older interpreters ignore the
# environment variable and are covered by the isolated directory above.
PYSAFE=""
python3 -P -c "pass" >/dev/null 2>&1 && PYSAFE="-P"

PYTHONSAFEPATH=1 python3 $PYSAFE -m pytest --ctrf /logs/verifier/ctrf.json -p no:cacheprovider /tests/test_outputs.py -rA
rc=$?
if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
