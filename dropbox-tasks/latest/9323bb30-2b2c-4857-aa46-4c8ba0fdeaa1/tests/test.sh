#!/usr/bin/env bash
# Isolate recompute helpers from candidate /app/bin/* during verification.
#
# Real helpers ship only as opaque tests/_verifier_lib.b64 (not importable Python).
# Decoded exclusively to /logs/verifier/kvtile-private for pytest PYTHONPATH.
# /opt/kvtile-verifier is kept as an empty stub directory — never holds .py helpers —
# so candidate binaries cannot read a reference implementation there.
# Top-level /tests/kvtile_recompute.py stubs remain ImportError.
# When permitted, bwrap/unshare still hides /tests from the pytest process tree.
set -uo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
echo '{}' > /logs/verifier/ctrf.json
TEST_DIR="${TEST_DIR:-/tests}"

if [ "$PWD" = "/" ]; then
  echo "workdir must not be /" >&2
  false
fi

# Verifier must invoke rebuild.sh (covers required rebuild behavior). Use
# KVTILE_VERIFIER_EPOCH_ONLY so oracle-installed bins are not replaced by stub cargo.
if [[ -x /app/scripts/rebuild.sh ]]; then
  KVTILE_VERIFIER_EPOCH_ONLY=1 bash /app/scripts/rebuild.sh
elif [[ -x /app/scripts/build.sh ]]; then
  bash /app/scripts/build.sh
else
  true
fi
if [ $? -eq 0 ]; then
  OPT_STUB="/opt/kvtile-verifier"
  PRIVATE="/logs/verifier/kvtile-private"
  SCRUB="/tmp/kvtile-pytest"
  HIDE="/tmp/kvtile-empty-tests"
  PROBE="/tmp/kvtile-isolation-probe.py"
  BLOB="${TEST_DIR}/_verifier_lib.b64"

  rm -rf "${OPT_STUB}" "${PRIVATE}" "${SCRUB}" "${HIDE}"
  mkdir -p "${OPT_STUB}" "${PRIVATE}" "${SCRUB}/fixtures" "${HIDE}"
  # Marker only — no Python helpers under the candidate-documented stub path.
  printf 'no reference implementation\n' > "${OPT_STUB}/README.txt"
  chmod 755 "${OPT_STUB}"
  chmod 644 "${OPT_STUB}/README.txt"

  /usr/bin/python3 - "${BLOB}" "${PRIVATE}" <<'PY'
import base64, sys, tarfile, io, pathlib
blob_path, out_dir = sys.argv[1], sys.argv[2]
if not pathlib.Path(blob_path).is_file():
    raise SystemExit(f"missing opaque verifier lib {blob_path}")
raw = base64.b64decode(open(blob_path, "r", encoding="ascii").read().strip())
with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
    tar.extractall(out_dir)
PY
  chmod 700 "${PRIVATE}"
  chmod 600 "${PRIVATE}/kvtile_recompute.py" "${PRIVATE}/reference_model.py"

  cp "${TEST_DIR}/test_outputs.py" "${SCRUB}/test_outputs.py"
  if [[ -d "${TEST_DIR}/fixtures" ]]; then
    cp -a "${TEST_DIR}/fixtures/." "${SCRUB}/fixtures/"
  fi

  cat > "${PROBE}" <<'PY'
import importlib.util
import sys

paths = [
    "/tests/kvtile_recompute.py",
    "/tests/reference_model.py",
    "/tests/.verifier_private/kvtile_recompute.py",
    "/tests/.verifier_private/reference_model.py",
    "/tests/.authoring_private/kvtile_recompute.py",
    "/tests/_artifact_recompute/kvtile_recompute.py",
    "/opt/kvtile-verifier/kvtile_recompute.py",
    "/opt/kvtile-verifier/reference_model.py",
]
for p in paths:
    try:
        spec = importlib.util.spec_from_file_location("probe", p)
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception:
        continue
    if hasattr(mod, "seal_digest") or hasattr(mod, "expect_seal"):
        sys.exit(7)
sys.exit(0)
PY

  if command -v bwrap >/dev/null 2>&1 && bwrap --die-with-parent --ro-bind /usr /usr --tmpfs /tmp -- /bin/true 2>/dev/null; then
    echo "verifier isolation mode=bwrap" >&2
    bwrap \
      --die-with-parent \
      --ro-bind /usr /usr \
      --ro-bind /lib /lib \
      --ro-bind-try /lib64 /lib64 \
      --ro-bind /bin /bin \
      --ro-bind /sbin /sbin \
      --ro-bind /opt /opt \
      --ro-bind /app /app \
      --bind /tmp /tmp \
      --bind /logs /logs \
      --tmpfs /tests \
      --dev /dev \
      --proc /proc \
      --setenv KVTILE_VERIFIER_LIB "${PRIVATE}" \
      --setenv TEST_DIR "${SCRUB}" \
      --setenv PYTHONPATH "${PRIVATE}" \
      --setenv KVTILE_APP_ROOT "${KVTILE_APP_ROOT:-/app}" \
      --setenv PATH "${PATH}" \
      --setenv HOME /tmp \
      --chdir /app \
      bash -c '
        set -uo pipefail
        /usr/bin/python3 /tmp/kvtile-isolation-probe.py || exit 1
        /opt/verifier-venv/bin/python -m pytest /tmp/kvtile-pytest/test_outputs.py -rA \
          --ctrf /logs/verifier/ctrf.json
      '
  elif unshare -m -- true 2>/dev/null; then
    echo "verifier isolation mode=unshare" >&2
    unshare -m -- env \
      KVTILE_VERIFIER_LIB="${PRIVATE}" \
      TEST_DIR="${SCRUB}" \
      PYTHONPATH="${PRIVATE}" \
      KVTILE_APP_ROOT="${KVTILE_APP_ROOT:-/app}" \
      PATH="${PATH}" \
      bash -c '
        set -uo pipefail
        mount --make-rprivate / 2>/dev/null || true
        if [[ -d /tests ]]; then
          mount --bind /tmp/kvtile-empty-tests /tests 2>/dev/null \
            || mount -t tmpfs -o size=1m tmpfs /tests 2>/dev/null \
            || exit 1
        fi
        /usr/bin/python3 /tmp/kvtile-isolation-probe.py || exit 1
        /opt/verifier-venv/bin/python -m pytest /tmp/kvtile-pytest/test_outputs.py -rA \
          --ctrf /logs/verifier/ctrf.json
      '
  else
    echo "WARN: mount isolation unavailable; stub + opaque-blob isolation" >&2
    /usr/bin/python3 "${PROBE}"
    if [ $? -eq 0 ]; then
      export KVTILE_VERIFIER_LIB="${PRIVATE}"
      export TEST_DIR="${SCRUB}"
      export PYTHONPATH="${PRIVATE}"
      /opt/verifier-venv/bin/python -m pytest "${SCRUB}/test_outputs.py" -rA \
        --ctrf "/logs/verifier/ctrf.json"
    else
      echo "isolation probe failed — known /tests import paths still expose helpers" >&2
      false
    fi
  fi
else
  false
fi
if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
