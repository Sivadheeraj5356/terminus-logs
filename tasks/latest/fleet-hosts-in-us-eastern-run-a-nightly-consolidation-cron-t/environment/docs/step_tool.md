# Offline rebuild tools

The environment ships two host-side helpers used to rebuild the daylight-saving schedule history after timezone transitions. Both are built from /app/environment and installed under /app/tools. Together they replay captured fragment snapshots for each transition window and pack the stepped artifacts into schedule_ledger.json.

## step_tool

step_tool drives one window at a time. It reads a pane index file for zone, cadence index, and anchor epoch, replays a trace snapshot into that window's out directory, and writes rows.tab plus a frags/ copy of the input fragments. Per-window state such as slot_state.rec for the backward window lands in the same out directory. The backward lane rebinds that state before every fragment, so collapse of the repeated autumn hour depends on the file contents, not on process-local memory.

Arguments:

- --pane names backward, forward, or resume and is stored in each emitted row's window field
- --env points at that pane's window index file, for example /app/data/windows/backward/window.conf, /app/data/windows/forward/window.conf, or /app/data/windows/resume/window.conf (not the shared m5s/cadence_policy.conf)
- --trace points at the captured fragment snapshot under /app/data/traces/
- --out is the directory receiving that window's stepped artifacts

## pack_tool

pack_tool walks rows.tab under each window subdirectory beneath a step root, assembles the rows array for schedule_ledger.json, and computes ledger_digest as described in ledger_format.md.

Arguments:

- --step-root is the directory containing backward/, forward/, and resume/ after stepping
- --out is the path of the JSON file to write, typically /app/output/schedule_ledger.json

## Typical rebuild sequence

After refreshing the schedule policy sources, rebuild the helpers and replay all three windows before packing:

```bash
make -C /app/environment clean all
cp /app/environment/build/step_tool /app/tools/step_tool
cp /app/environment/build/pack_tool /app/tools/pack_tool

/app/tools/step_tool --pane backward --env /app/data/windows/backward/window.conf --trace /app/data/traces/backward.rows --out /app/output/step/backward
/app/tools/step_tool --pane forward  --env /app/data/windows/forward/window.conf  --trace /app/data/traces/forward.rows  --out /app/output/step/forward
/app/tools/step_tool --pane resume   --env /app/data/windows/resume/window.conf   --trace /app/data/traces/resume.rows   --out /app/output/step/resume
/app/tools/pack_tool --step-root /app/output/step --out /app/output/schedule_ledger.json
```

The commit log and boot-era marker under /app/output/step are shared for the duration of one rebuild run, so stepping the windows individually before a single pack_tool invocation produces the same ledger_digest as stepping them in one batch. Because the digest is derived from the row set, hand-edited output is easy to spot once the canonical line blob no longer matches ledger_digest.
