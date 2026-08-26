The leak repro is useful, but now I need the actual fix. Update the Rust host/component boundary code under /app so /app/tools/run-fixed.sh cleans up transient stream-read errors instead of leaving descriptors and queued errors behind.

The fixed report should go to /app/reports/fault-fixed.json and use the same report shape, SHA-256 fields, audit rows, and environment controls as the leak report, except mode should be "wasi-error-cleanup" and leaked_descriptors should be 0. Faults should still happen, fallback re-reads should preserve the packed output hash, and cleanup should handle default cadence, FAULT_EVERY, FAULT_PATTERN, STREAM_ROUNDS, and PACK_CHUNK runs without leaving queued errors behind.

The cleanup needs to be generation-aware: duplicate, stale, or unrelated queued stream errors must not double-count drops or close the wrong stream after a descriptor number is reused.
