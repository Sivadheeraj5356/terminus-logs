# Rotation segment replay

Fixture segments under `/app/fixtures/rotation-segment/segments.jsonl` describe rotation generations used when incremental valuation journal replay is active. Each segment row carries a `rotation_id` integer used when classifying replay windows.

## Window binding

`shed_weave.compile_window.classify_segment` decides whether a segment participates in the active replay window. The replay window cutoff and rotation floor depend on whether incremental mode is enabled.

## Replay floor

`shed_weave.phase_journal.replay_floor_for_window` derives the guild_assignment epoch replay floor from active segments. Attestation coverage must slice clipped export_routes epochs from this floor before per-year certificate evaluation when incremental replay is active.

## Environment switches

- `TRACE_INCREMENTAL=1` — incremental journal replay pass (rotation fixtures + replay floor)
- `TRACE_HALT=1` — interrupted valuation (journal snapshot only; `--out` is not written)
- `TRACE_RESUME=1` — resume from halt journal when `network_seal` matches a fresh compile

Incremental and full compiles on the same bundle must agree when registries are unchanged.
