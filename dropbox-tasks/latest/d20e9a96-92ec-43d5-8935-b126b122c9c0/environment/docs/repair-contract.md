# Repair report contract

The restore tool outputs a JSON provenance log at the path given by `--log`. The top-level structure groups per-lab span records under a `repositories` key:

```json
{
  "target": "<snapshot name>",
  "repositories": {
    "<lab>": [ ... ]
  }
}
```

Each lab array contains one object per recipe `part` row in the lab's recipe file. Each object has five keys: `path`, `span`, `bytes`, `status`, `source`.

The `status` field is one of `indexed`, `scanned`, or `merged`.

## Restore tree paths (fieldday snapshot)

| lab | path |
|-----|------|
| atlas | atlas/home/manifest.txt |
| atlas | atlas/home/window.log |
| beacon | beacon/logs/uplink.txt |
| beacon | beacon/logs/routes.txt |
| cinder | cinder/ledger/day.txt |
| ridge | ridge/trail/summary.txt |
| ridge | ridge/trail/borrow.txt |
| mesa | mesa/ops/radio.txt |
| mesa | mesa/ops/relay.txt |

## Neighbor snapshot drill

After repairing the fieldday restore, the utility must also complete neighbor drills without mutating lab fixtures:

```bash
cargo run -- run --root /app/labs --name steady-2026-06-17 --out <directory> --log <json>
```
