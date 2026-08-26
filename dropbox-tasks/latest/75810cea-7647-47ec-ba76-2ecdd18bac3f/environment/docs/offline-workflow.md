# Offline workflow

Required command order for a clean seal:

1. `pnpm run resume` — close an incomplete migrate tip in `/app/state/migrate-journal.jsonl`
2. `pnpm run seal` — recompute plan, rewrite lockfile/manifests, replace offline store
3. `pnpm install --offline --frozen-lockfile` — materialize importer `node_modules` links
4. `pnpm run build` — emit `/app/reports/build-summary.json`
5. `pnpm run audit:seal` — emit `/app/reports/seal-audit.json`

`pnpm run verify:all` runs that sequence.

Replay checks may delete generated surfaces under `/app/generated`,
`/app/offline-store/tarballs`, `/app/offline-store/index.json`, `/app/reports`,
and importer `node_modules` trees. The pipeline must regenerate them; static
hand-writes are insufficient.
