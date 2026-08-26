During fat-jar packaging and dependency shading the shipped package relocation consistency validator must analyze twenty bundled packaging relocation batches under /app/reloc-batches that model Maven-shade style dependency namespace remaps across jar artifacts and write one packaging CI report to /app/artifacts/relocation_consistency_report.json.

Implement EvaluateBatch in /app/reloclogic/evaluate.go using /app/RELOCATION_SPEC.md, /app/REPORT_LAYOUT.md, and /app/reloc-canon/rules.yaml.

Mandatory encodings and hard policy rules (normative details and abstract examples are in RELOCATION_SPEC — do not invent alternatives):
- Every finding `rule_id` MUST be exactly `reloc.<kind>` (never the bare kind).
- `isolation_breach.subject` MUST be dotted package form (e.g. `shaded.shared`), never slash form.
- Findings MUST be globally sorted by `(kind, subject, expected, observed)` after dedupe.
- Digest `|maps|` binding uses effective full-batch mappings joined in ascending `seq` order (NOT lex). Exclude stale, shadowed, AND any mapping whose `from_prefix` appears on a `relocation_loop` cycle when `digest_exclude_cycle_maps` is true (cycle nodes are dropped from `map_bind` even when still used as prefixes).
- Successful applies still append `|maps|` when the effective list is empty.
- `relocator_epoch_must_equal`: observed epoch must equal required epoch exactly.
- Orphan residuals: scan each `observed.nested` entry for parent P independently; emit at most one `orphan_nested_observation` for P if any entry has payload (symbols or refs). Empty shells never count. A parent with only empty shells under `cascade_gap` emits gap but not orphan. For that finding, `expected` MUST be `""` and `observed` MUST be the literal string `present` (never `residual` or other synonyms).
- Dangling observations cover top-level unknown symbol originals, unknown ref ids (`ref:<id>`), AND unknown nested observed originals with subject `parent_path#original`.
- Replay: skip digest checks; empty `mapping_seq_order` means zero maps; unknown seq values in a schedule are ignored for subset selection and for prefix/full length checks.
- Replay `stable`: when the full batch has findings and every schedule spans the full mapping count, `full_unstable_on_findings` forces `stable` to `false` even if every schedule passed.
- Nested-only symbol collisions must not emit `symbol_collision` when `collision_top_level_only` is true.

Also honor longest prefix remaps, shadowed mappings, cascade gap nested suppression, resource rewrite checks, resource-bound digest seeds, preserve_identity_version, and rollback digests. Keep /app/relocbin/main.go and the remaining reloclogic helpers unchanged. Empty finding lists must be JSON arrays never null. The packaging binary at /app/bin/reloccheck must exceed 2048 bytes.

Do not modify bundled packaging batches, specification documents, or the canon file. Derive every packaging verdict from evaluation of the inputs. Honor RELOC_BATCH_DIR when set.
