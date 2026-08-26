# Build notes

Offline Node TypeScript workspace under `/app/environment`.

```bash
cd /app/environment
npm install --no-audit --no-fund
npm run build
```

Compiled JavaScript lands in `dist/`. The score driver is `dist/pilot/server.js`.

Run score export:

```bash
/app/tools/k9ctl score
```

This deletes `/app/output/blk_k9.json` and `/app/output/trace_w8.jsonl`, rebuilds if needed, replays catalog rotations, and writes hold-store digests under `/app/output/run_traces/`.

Precheck-only mode (staging slice):

```bash
node dist/pilot/server.js precheck
```

Hold parity helper:

```bash
python3 /app/environment/hold/ref_hold.py parity_fp <cover_hex> <merge_hex> <block_hex>
```
