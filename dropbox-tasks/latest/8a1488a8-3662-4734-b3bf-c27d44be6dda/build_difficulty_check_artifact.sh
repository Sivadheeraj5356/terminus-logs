#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${ROOT}/../../Task_Ready_To_Submit/overlay-patch-closure-skew-difficulty_check_artifact.zip"
STAGING="$(mktemp -d)"
IMAGE="opcs-test"
trap 'rm -rf "${STAGING}"' EXIT

docker build --platform linux/amd64 -t "${IMAGE}" -f "${ROOT}/environment/Dockerfile" "${ROOT}/environment"

mkdir -p "${STAGING}/tests" "${STAGING}/logs/verifier"
cp "${ROOT}/tests/test.sh" "${ROOT}/tests/test_outputs.py" "${STAGING}/tests/"

docker run --rm --platform linux/amd64 \
  -v "${ROOT}/solution:/solution:ro" \
  -v "${STAGING}/tests:/tests:ro" \
  -v "${STAGING}/logs:/logs" \
  "${IMAGE}" bash -c 'bash /solution/solve.sh && bash /tests/test.sh' \
  > "${STAGING}/test-stdout.txt" 2>&1

cp "${STAGING}/logs/verifier/ctrf.json" "${STAGING}/ctrf.json"
cp "${STAGING}/logs/verifier/reward.txt" "${STAGING}/reward.txt"

docker run --rm --platform linux/amd64 \
  -v "${STAGING}/tests:/tests:ro" \
  -v "${STAGING}/logs:/logs" \
  "${IMAGE}" bash -c 'find /app/cmd /app/internal -name "*.go" -delete 2>/dev/null || true; rm -rf /app/bin/cl_publish /app/output/closure_report.json; bash /tests/test.sh' \
  > "${STAGING}/nop-test-stdout.txt" 2>&1 || true

rm -f "${OUT}"
(
  cd "${STAGING}"
  zip -rq "${OUT}" tests ctrf.json test-stdout.txt nop-test-stdout.txt reward.txt
)

echo "Wrote ${OUT}"
unzip -l "${OUT}"
