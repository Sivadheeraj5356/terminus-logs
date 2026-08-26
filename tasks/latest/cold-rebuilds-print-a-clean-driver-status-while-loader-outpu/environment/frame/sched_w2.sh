#!/usr/bin/env bash
fn_r3() {
  local journal_in="$1"
  local hook_epoch="$2"
  python3 - "$journal_in" "$hook_epoch" <<'PY'
import json, sys
from pathlib import Path
journal = json.loads(Path(sys.argv[1]).read_text())
hook_epoch = int(sys.argv[2])
commits = []
for seg in journal.get("segments", []):
    blob_epoch = int(seg.get("blob_epoch", 0))
    hook_gen = int(seg.get("hook_gen", 0))
    if blob_epoch + 1 >= hook_gen:
        commits.append({"lane": seg["lane"], "hook_epoch": hook_epoch, "committed": True})
    else:
        commits.append({"lane": seg["lane"], "hook_epoch": hook_epoch, "committed": False})
Path("/app/.staging/hook_state.json").write_text(json.dumps({"commits": commits}, indent=2) + "\n")
PY
}
