# Bring the CI runner cgroup v2 job-sandbox attach service under `/app/environment

- **UUID:** `4e8a157c-e3d3-44d0-bb7d-600de063f6fd`
- **Slug:** `bring-the-ci-runner-cgroup-v2-job-sandbox-attach-service-und`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

Bring the CI runner cgroup v2 job-sandbox attach service under `/app/environment` back into operational compliance for nesting policy. Follow the documented procedure: build with `/app/environment/k4m/build_wrap.sh /app/environment /app/bin/cg_xmit`, then rematerialize `/app/output/protocol_transcript.json` with `/app/bin/cg_xmit` from the pinned hierarchy annex and the nesting arm catalog.

Hierarchy migrate packing, durable controller claim, nest handshake combine, and transcript emit must stay synchronized so the attach pipeline rematerializes a coherent operational artifact. A static transcript file is not an accepted substitute for the build_wrap plus `cg_xmit run` rematerialization path; static or manual output writes are insufficient, including hand-placed latch journal or accept stamp files under `/app/environment/engine/seg_v`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
