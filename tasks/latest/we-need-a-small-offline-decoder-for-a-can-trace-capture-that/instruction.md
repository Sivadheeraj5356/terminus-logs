We need a small offline decoder for a CAN trace capture that came off a bench rig. Build a Go CLI at `/app/cantrace` that reads the network description and binary trace, applies the validation rules in `/app/task_file/cantrace-format.md`, and writes the JSON report.

Running `/app/cantrace` with no arguments must read `/app/task_file/network.json` and `/app/task_file/public_trace.bin`, then write `/app/out/report.json`. Running `/app/cantrace <network.json> <trace.bin> <report.json>` must do the same job for another compatible capture. The verifier uses exact JSON values after parsing, so field names, lowercase reason strings, null values, ordering, and numeric values need to match the spec exactly.

Keep the tool self-contained and offline. Empty traces, messages with no decoded samples, unknown frame IDs, checksum failures, DLC failures, stale valid-frame gaps, counter jumps, counter rollover, little- and big-endian signed bit fields, and multiplexed signals are all valid cases and should be reported as described rather than treated as crashes.

When you call the explicit three-argument mode, the report path may point to new directories that don't exist yet; the CLI must create those parent directories before writing.
