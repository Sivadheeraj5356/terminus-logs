# Operator guide

## CLI

```
modpolicylock resolve  --request PATH --goos OS --goarch ARCH --lock OUT --db PATH [--root PATH]
modpolicylock report   --request PATH --goos OS --goarch ARCH --report OUT --db PATH [--root PATH]
modpolicylock reindex  --mirror PATH --db PATH [--resume]
modpolicylock migrate-lock --in PATH --out PATH
modpolicylock verify   --lock PATH --report PATH
```

## Harness

`/app/scripts/offline-modpolicy.sh` reindexes when needed, resolves, reports, and verifies:

```bash
/app/scripts/offline-modpolicy.sh \
  --request /app/workspaces/smoke/request.json \
  --goos linux --goarch amd64 \
  --lock /output/modpolicy.lock.json \
  --report /output/policy-report.json
```

## Diagnostics

Missing or unauthorized modules exit `23` with stderr containing `unauthorized or missing module`.

## Paths

- Mirror: `/app/var/module-mirror/`
- Policy index DB: `/app/var/policy-index/policy.db`
- Workspaces: `/app/workspaces/`
- Optional ephemeral roots used in drills: `/tmp/tb3-modpolicy-root`, `/tmp/tb3-clean.db`, `/tmp/tb3-resume.db`, `/tmp/tb3-partial-policy.db`, `/tmp/bad-request.json`
- Alternate artifact names under `/output/`: `modpolicy-amd64.lock.json`, `modpolicy-arm64.lock.json`, `modpolicy-clean.lock.json`, `policy-report-clean.json`, `offline.lock.json`, `offline-report.json`, `bad.lock.json`, `bad-report.json`

## Digest probe

`/app/scripts/digest_probe.py` recomputes `resolution_digest` from a lock or report using the rules in `/app/docs/REPRO_DIGEST.md`.

Verifier drills may set `TB3_MODPOLICY_SEED` for deterministic generated requests. The seed drives a pseudo-random choice of workspace alias (`alpha`, `beta`, or `gamma`) and target `goarch` (`amd64` or `arm64`). Each generated workspace is a minimal `go.work` overlay on `corp.example/root` requiring `corp.example/lib`; resolution must follow the same precedence and mirror rules as bundled fixtures under `/app/workspaces/`.

The interrupt-reindex drill (`/app/scripts/interrupt-reindex.sh`) intentionally leaves a partial policy database with `index_meta.index_complete=1` while fewer pin rows exist than `policy/pins.jsonl` contains. Repair must finish indexing without treating that partial shape as healthy output.
