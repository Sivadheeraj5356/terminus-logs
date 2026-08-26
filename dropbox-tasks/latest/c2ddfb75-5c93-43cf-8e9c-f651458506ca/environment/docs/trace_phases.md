# Compile phases

The pattern genealogy trace walks each bundle through a fixed phase chain. Later phases consume views materialized during earlier phases; reordering or skipping a phase changes downstream totals even when individual helpers appear correct in isolation.

1. **Context bind** — Resolve bundle policy family, active blend coefficients, snapshot cutoff year (if any), and network seal inputs. Registry digest materialization for the seal must use the same dye-recipe amendment overlay merge as compile-time registry loading. See `/app/docs/tint_order_policy.md`.

2. **Trace lane profile** — Bind genealogy blend for the current trace only. Do not reuse session-scoped blend tables across consecutive traces in one interpreter.

3. **Materialize** — Join catalog alias rows to canonical registry slices for dye reformulations, export routes, loom letters, merchant transfers, school recitals, and pattern anchors.

4. **Dye lane sequencer** — Clip snapshot timelines, gate dye events by export eligibility and school recital evidence, then compound restoration fidelity multiplicatively. Honor `reset_drift` rows and sequential drift seeds from earlier panels when `panel_coupling` is `sequential_drift`. Gating must precede compounding.

5. **Lineage** — Compile workshop succession for the panel completion year, then walk thread-trust coefficients along the mentor chain.

6. **Attestation** — Measure per-calendar-year certificate coverage across clipped export-route spans, including merchant-transfer-gated certificate relay on transfer years.

7. **Assembly** — Combine lineage, dye fidelity, and attestation terms into heritage score and influence index rows.

Rotation fixture segments under `/app/fixtures/rotation-segment/` participate in incremental replay when `TRACE_INCREMENTAL=1` is set. See `/app/docs/rotation_segments.md`.

Run traces with:

`python3 -m shed_weave.cli trace --bundle <path> --out /app/output/pattern_genealogy.json`
