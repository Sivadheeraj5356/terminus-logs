# Replay journal contract

Each scenario owns `/app/state/<scenario>.journal` and `<scenario>.lock`. The CLI also accepts `--state-dir DIR`, `--output PATH`, and `--no-resume`.

The journal is append-only. A committed record contains, in order: packed little-endian header fields `magic=0x54454c4a`, `version=2`, total record length, PID count, generation, a 64-character lowercase input fingerprint plus NUL, replay counters, and scenario id; then `pid_count` unsigned 64-bit PIDs; then CRC32C over header and PID bytes. Writes must be complete and durable before releasing the per-scenario advisory lock.

Startup scans from byte zero. The last fully readable, structurally valid, CRC-valid record is the recovery point. A partial header, partial body, impossible length/count, bad magic/version, or CRC mismatch marks a corrupt tail. The implementation must truncate exactly to the end of the last valid record and continue. `recovered_records` is the number of valid records retained when such truncation occurred, otherwise zero.

The input fingerprint is SHA-256 over the exact bytes of `data.mdb`, the exact bytes of `/app/config/replayer.toml`, the scenario id bytes, and the native `int` loop count bytes, concatenated in that order. A record is reusable only when its fingerprint equals the current fingerprint. A cache hit must reproduce semantic replay fields without reopening LMDB. `--no-resume` disables reuse but still performs recovery and appends a new generation.

Generations are per scenario and monotonic. A cold journal starts at generation 1. Cache hits retain the generation. A cache miss or forced replay appends `last_valid_generation + 1`. Concurrent invocations for one scenario must serialize so only one cold computation is committed; other identical invocations reuse it. Different scenarios never share locks or journals.
