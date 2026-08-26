#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib_boot.sh"

boot_paths
export OUT_ROOT ENV_ROOT WORK_ROOT
mkdir -p "${OUT_ROOT}" "${WORK_ROOT}"
CLS_ROOT="${WORK_ROOT}/classes"
mkdir -p "${CLS_ROOT}"
SRC_LIST="${WORK_ROOT}/sources.lst"

find "${ENV_ROOT}" \( -path '*/target/*' -o -path '*/.git/*' \) -prune -o -type f -name '*.java' -print \
  | sort > "${SRC_LIST}"
javac --release 21 -d "${CLS_ROOT}" @"${SRC_LIST}"

java -cp "${CLS_ROOT}" gp.u3.StageA
java -cp "${CLS_ROOT}" gp.v6.StageB
java -cp "${CLS_ROOT}" hz.w1.StageC
