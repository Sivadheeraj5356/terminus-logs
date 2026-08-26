# Thin link workspace layout

The lane under `/app/environment` builds a multi-translation-unit C++ binary with a generated gate header. Workspace roots:

- `/app/work/gen` — generated `gate_abi.h`, `gate_abi.cpp`, and `abi_stamp.txt`
- `/app/work/obj` — per-module object files (`anchor.o`, `consumer.o`, `dispatch.o`, …)
- `/app/work/lto` — thin summary sidecars such as `dispatch.summary.json` and `consumer.summary.json`, plus `epoch_journal.json` tracking the active link generation
- `/app/work/bin/matrix_app` — linked binary; `matrix_app --probe` prints lane, ABI tag, seed, and mixed values
- `/app/work/checkpoint` — sidecar snapshots and `manifest.json` used by replay passes (`pass3.sh`, `pass4.sh`)
- `/app/output/link_report.json` — optional incremental report from `tu_orchestrator.py --report`

Cold pass wipes `/app/work` via `bash /app/environment/scripts/reset_workspace.sh`, runs a full link through `/app/environment/auxiliary/tu_orchestrator.py`, then records observations. Incremental passes reuse the workspace and call `tu_orchestrator.py --mode incremental`.

Python helpers expect `PYTHONPATH=/app/environment`. The orchestrator accepts `--mode {full,incremental}`, `--profile release`, and optional `--report <path>` (JSON with `relinked_modules`, `summary_hash`, and `binary`). Observation emission uses `python3 /app/environment/ci/observation_emit.py --pass <scenario> [--append]` to write `/app/output/lto_observation.json`. JSON sidecars, profiles, and observation output use UTF-8 text encoding. Exported symbols are collected with `nm --defined-only --format=posix` on the linked binary. Release linker settings in `/app/environment/compile/toolchain.cmake` may include auxiliary flags such as `-Wl,--hash-style=gnu`.

Pass scripts live under `/app/environment/ci/harness/` (`pass0.sh`, `pass1.sh`, `pass2.sh`, `pass3.sh`). Ordered pass lists are in `/app/environment/ci/sequences.json`.

Python orchestration code lives under `/app/environment/auxiliary/`; LTO sidecar helpers live under `/app/environment/lto/`.
