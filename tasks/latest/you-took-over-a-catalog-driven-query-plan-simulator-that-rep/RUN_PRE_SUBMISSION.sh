#!/usr/bin/env bash
# Run from repo root: bash tasks/stats-plan-resume-skew/RUN_PRE_SUBMISSION.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TASK="tasks/stats-plan-resume-skew"
TASK_DIR="${ROOT}/${TASK}"
IMAGE="stats-plan-resume-skew-preverify"
cd "${ROOT}"

echo "== Clean local verifier artifacts =="
rm -rf "${TASK_DIR}/tests/.venv" "${TASK_DIR}/tests/.pytest_cache"

echo "== Static checks =="
python3 run_static_checks.py --task-dir "${TASK}" --version edition_2

echo "== Instruction audit =="
python3 instruction_audit.py "${TASK}"

echo "== Collapse check (WARN is acceptable for legacy tasks) =="
python3 collapse_check.py "${TASK}" || [[ $? -le 2 ]]

echo "== Docker build =="
docker build -t "${IMAGE}" "${TASK_DIR}/environment"

echo "== Oracle (docker) =="
docker run --rm \
  -v "${TASK_DIR}/solution:/solution:ro" \
  -v "${TASK_DIR}/tests:/tests" \
  "${IMAGE}" \
  bash -c 'bash /solution/solve.sh >/dev/null 2>&1 && bash /tests/test.sh && cat /logs/verifier/reward.txt'

echo "== NOP broken baseline (docker, expect 0) =="
docker run --rm \
  -v "${TASK_DIR}/tests:/tests" \
  "${IMAGE}" \
  bash -c '/app/ci/build_and_load.sh >/dev/null 2>&1; bash /tests/test.sh; cat /logs/verifier/reward.txt'

echo "== Clean verifier artifacts after docker runs =="
rm -rf "${TASK_DIR}/tests/.venv" "${TASK_DIR}/tests/.pytest_cache"

echo "== Package zip =="
rm -f Task_Ready_To_Submit/stats-plan-resume-skew.zip
(cd "${TASK}" && zip -rq "../../Task_Ready_To_Submit/stats-plan-resume-skew.zip" . \
  -x '*/__pycache__/*' '*.pyc' \
  -x 'output_contract.toml' 'quality_check_adjudication.json' \
  -x 'rubric.txt' 'rubrics.txt')
python3 validate_submission_zip.py Task_Ready_To_Submit/stats-plan-resume-skew.zip

echo "== Approval gate =="
python3 approve_task.py --task-dir "${TASK}" \
  --zip Task_Ready_To_Submit/stats-plan-resume-skew.zip \
  --skip-verifier-health

echo "Done. Upload Task_Ready_To_Submit/stats-plan-resume-skew.zip to Snorkel."
