# q7m replay workspace

Games repair task.

Terminal driver at `/app/environment/bin/q7m` serves as the play client. The bundled referee in `docs/k9_rules.md` documents output contracts. Each run emits a `transcript.jsonl` graded transcript row per ply.

Rebuild with `bash /app/environment/scripts/build_q7m.sh` before every observation or repair run.
