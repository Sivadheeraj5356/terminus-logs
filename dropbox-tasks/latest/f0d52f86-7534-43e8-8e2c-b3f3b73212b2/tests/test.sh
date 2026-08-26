#!/bin/bash
mkdir -p /logs/verifier
cd /app

# Anti-gaming: when the verifier runs as root (the graded image), strip all
# non-owner access to the verifier assets and to the Python/NumPy runtime so the
# candidate binary - executed as an unprivileged user by the test suite - cannot
# read the reference, fixtures, or tolerances, nor exec an interpreter to
# fabricate a trace. Root (the suite itself) keeps full access, so grading is
# unaffected. Off-root local runs skip this and behave identically.
if [ "$(id -u)" = "0" ]; then
  chmod 700 /tests 2>/dev/null
  chmod -R go-rwx /tests/reference.py /tests/fixtures /tests/baselines 2>/dev/null
  chmod o-rwx /usr/bin/python3* /usr/local/bin/python3* 2>/dev/null
  NPDIR=$(python3 -c "import numpy,os;print(os.path.dirname(numpy.__file__))" 2>/dev/null)
  if [ -n "$NPDIR" ]; then chmod -R o-rwx "$NPDIR" 2>/dev/null; fi
fi

python3 -m pytest -rA -x /tests/test_outputs.py
if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
