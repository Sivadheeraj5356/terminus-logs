#!/bin/bash
# shellcheck source=/dev/null
source "$(dirname "$0")/../../scripts/env.sh"

run_build() {
  local mode="$1"
  export PATH="/app/environment/ci/fake_bin:${PATH}"
  PYTHONPATH=/app/environment python3 /app/environment/auxiliary/tu_orchestrator.py --mode "${mode}" --profile "${PROFILE}"
}

emit_observation() {
  local pass_name="$1"
  local append_flag=()
  if [[ "${2:-}" == "--append" ]]; then
    append_flag=(--append)
  fi
  PYTHONPATH=/app/environment python3 /app/environment/ci/observation_emit.py --pass "${pass_name}" "${append_flag[@]}"
}

touch_template_seed() {
  python3 - <<'PY'
import json
from pathlib import Path
profile = Path("/app/environment/gen/abi_profile.json")
data = json.loads(profile.read_text(encoding="utf-8"))
data["dispatch_seed"] = int(data["dispatch_seed"]) + 1
profile.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
}

touch_abi_profile() {
  python3 - <<'PY'
import json
from pathlib import Path
profile = Path("/app/environment/gen/abi_profile.json")
data = json.loads(profile.read_text(encoding="utf-8"))
tag = str(data["abi_tag"])
if not tag.endswith("-rev"):
    data["abi_tag"] = tag + "-rev"
profile.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
}

clean_workspace() {
  bash /app/environment/scripts/reset_workspace.sh
}

checkpoint_sidecars() {
  python3 - <<'PY'
import shutil
import sys
from pathlib import Path

sys.path.insert(0, "/app/environment")
from auxiliary import replay_ledger

work = Path("/app/work")
staging = Path("/tmp/lto_sidecar_checkpoint")
if staging.is_dir():
    shutil.rmtree(staging)
staging.mkdir(parents=True, exist_ok=True)

profile = Path("/app/environment/gen/abi_profile.json")
(staging / "abi_profile.json").write_text(profile.read_text(encoding="utf-8"), encoding="utf-8")

lto_src = work / "lto"
if lto_src.is_dir():
    shutil.copytree(lto_src, staging / "lto")

gen_src = work / "gen"
if gen_src.is_dir():
    shutil.copytree(gen_src, staging / "gen")

replay_ledger.write_checkpoint(work, lto_src, profile)

checkpoint = work / "checkpoint"
if checkpoint.is_dir():
    shutil.copytree(checkpoint, staging / "checkpoint")

shutil.rmtree(work, ignore_errors=True)
work.mkdir(parents=True, exist_ok=True)
shutil.copytree(staging / "lto", work / "lto")
shutil.copytree(staging / "gen", work / "gen")
if (staging / "checkpoint").is_dir():
    shutil.copytree(staging / "checkpoint", work / "checkpoint")
profile.write_text((staging / "abi_profile.json").read_text(encoding="utf-8"), encoding="utf-8")
replay_ledger.sync_journal_on_restore(work, work / "lto")
PY
}
