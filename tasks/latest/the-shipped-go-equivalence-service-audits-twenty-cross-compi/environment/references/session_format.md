# Build session input format

Load `build_*.json` from `/app/build-sessions/` unless the environment variable
`EQUIV_SESSION_DIR` points at another directory. Only analyze `build_01.json` through
`build_20.json` by `session_id`; ignore any other `build_*.json` in that directory.

Each session file:

```
{
  "session_id": "build_XX",
  "cross_compile": bool,
  "toolchains": [ { "id": string, "triple": string } ],
  "checkpoints": [
    {
      "seq": int,
      "stage": string,
      "toolchain": string,
      "artifact_hash": string,
      "symbol_digest": string,
      "compressed_size": int,
      "raw_size": int
    }
  ],
  "events": [
    {
      "seq": int,
      "toolchain": string,
      "stage": string,
      "op": "emit",
      "artifact_ref": string,
      "prev_hash": string,
      "new_hash": string,
      "symbol_digest": string
    }
  ],
  "rollbacks": [
    {
      "attempt": int,
      "failed_stage": string,
      "restored_checkpoint": int,
      "expected_symbol_digest": string,
      "actual_symbol_digest": string
    }
  ],
  "shards": [
    {
      "shard_id": string,
      "worker": string,
      "event_seqs": [ int ],
      "contribution_hash": string
    }
  ],
  "optimization_passes": [
    {
      "pass_id": string,
      "toolchain": string,
      "behavior_fingerprint": string
    }
  ],
  "stress": {
    "schedules": [
      { "schedule_id": string, "event_seq_order": [ int ] }
    ]
  }
}
```

Process events in ascending `seq`, tie-breaking by `toolchain` ascending.

Shard `contribution_hash` is SHA256 of member event `new_hash` values joined with NUL bytes
in `event_seq_order` sequence. The join is **NUL-terminated**: insert a single `\0`
byte after every value, including the last one. See `/app/contracts/OUTPUT_SCHEMA.md`
for output shape.
