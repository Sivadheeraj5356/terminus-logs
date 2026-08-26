# Thermal cycle trace-load contract

Thermal cycle batches live under /app/kiln-run-traces/ or any directory passed as --kiln-traces. Trace directories may contain sidecar files that are not traces, including JSON configuration tables such as conching-window-table.json or formulation-catalog.json placed beside the batch files. Trace load must scan only basename matches of *.jsonl under that directory, in ascending path sort order, and must ignore every non-jsonl sidecar. Do not parse *.json files or other extensions from the kiln-traces directory as events. Each JSONL line is one event with batch_id, formulation_id, cycle_seq, ts, temp_c, event, shear_hz, and duration_s.

Events with event MARKER are audit annotations only. They must not enter peak-capture hold profiles, and they must not count toward event_count on each batches row (event_count is the number of non-MARKER events for that batch_id).

Trace sequence is batch_id ascending, then cycle_seq ascending, then ts ascending within a cycle. This sequence drives peak-capture batch assembly and downstream residual scoring.

HOLD events inside a declared polymorph temper window contribute effective hold seconds. When shear_hz meets or exceeds the shear_bonus_hz from /app/conching-network/conching-window-table.json, effective hold adds ten percent of duration_s as bonus hold credit per /app/docs/walk-seal-bind.md.

Bundled kiln traces include batch identifiers ALPHA-01, BETA-02, and GAMMA-03. Hidden probe poison-batch-trap supplies batch TRAP-99 for ZONE-B6 residual checks. Hidden probe trace-order-trap stores later cycle_seq rows with earlier ts fields so loaders that sort only by ts field diverge from the batch_id / cycle_seq / ts sequence.

The trace-load stage writes /app/state/dsc-peak-capture.json with schema thermal-cycle-capture-v1. Top-level keys are schema, batches, and capture_digest only. Each batches row carries batch_id, formulation_id, event_count, and hold_profiles. Each hold_profiles row carries polymorph, effective_hold_s, and temp_c for one qualifying HOLD event. capture_digest is SHA-256 over stable JSON of batches and schema only. Wire example: /app/spec/dsc-peak-capture.schema.json

Stable JSON for digests means compact separators with no extra whitespace, object keys sorted ascending at every nesting level (Perl JSON::PP key-ordered), and whole-number numeric values encoded as JSON integers the way Perl JSON::PP does (149 not 149.0). The same stable JSON rules apply to capture_digest, snapshot_digest, chronicle_digest, and walk_content_digest.
