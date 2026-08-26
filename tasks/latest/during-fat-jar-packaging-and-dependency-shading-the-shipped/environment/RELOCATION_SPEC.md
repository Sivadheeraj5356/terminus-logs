# Relocation evaluation contract

Analyze each `batch_NN.json` under the batch directory. Apply relocation
mappings, compare observed transformed state, and emit findings.

## Mapping order

Sort `mappings` by `ordering.primary_key` (`priority` ascending) then
`ordering.secondary_key` (`from_prefix` ascending) from
`/app/reloc-canon/rules.yaml`. Equal priorities are common; the secondary key
is required.

## Longest prefix relocate

For a dotted name `s`, select the matching mapping whose `from_prefix` is a
prefix of `s` (or equals `s`) with the greatest `from_prefix` length. On length
ties, keep the earlier mapping in the sorted mapping list. Replace that prefix
with `to_prefix`.

If `chain_relocations` is true in the canon, repeat until a fixpoint. If a
value revisits a prior form during chaining, stop and treat the mapping set as
looping for that seed (see `relocation_loop` emission below for graph cycles;
chaining revisits do not themselves emit a separate finding).

Slash paths use the same rule after converting dots to slashes on both the
subject and each mapping prefix (`com.acme` to `com/acme`).

Never relocate using a mapping that is not present in the active mapping set.

## Mapping graph cycles

Build a directed graph with an edge `from_prefix -> to_prefix` for every active
mapping. If any cycle exists, emit exactly one `relocation_loop` finding.

Normative `relocation_loop` encoding (do not invent alternatives):

- `subject` is the full closed cycle path string, not a single node. Start at the
  lexicographically smallest node on the cycle, walk unique successors, and
  close the walk so the first node equals the last. Join nodes with the
  literal `>` character and no spaces. Worked example for `com.a -> com.b` and
  `com.b -> com.a`: `subject` is `com.a>com.b>com.a` (never `com.a` alone and
  never `com.a,com.b`).
- `expected` is always `""`.
- `observed` is always `""`.

When a cycle exists, still evaluate every other finding kind on the active set.
In particular, `stale_mapping` remains independent: a mapping that participates
in a cycle is still stale when its `from_prefix` is not a prefix of any symbol
fqn, ref literal, or resource content_ref. Do not suppress stale just because a
loop was found.

## Expected transforms

For each unit symbol, `expected_fqn` is relocate(symbol.fqn) under active
mappings. `expected_path` is relocate_path(symbol.pkg_path). They must agree:
convert `expected_fqn` package (everything before the final `.` segment) to
slashes; if that value differs from `expected_path`, emit `namespace_drift`
with `subject` equal to the original fqn, `expected` equal to the slash form
of the relocated package, and `observed` equal to `expected_path`.

For each unit ref, `expected_literal` is relocate(ref.literal).

For each unit resource, `expected_content` is relocate(resource.content_ref)
and `expected_res_path` is relocate_path(resource.path) when the path contains
a slash-mapped prefix; otherwise the path is unchanged.

## Observed comparisons

Use `observed.symbols`, `observed.refs`, and `observed.resources` keyed by
original fqn, ref id, and resource path respectively.

- `reference_omission`: expected literal differs from original, observed
  literal equals the original (unmoved), `subject` is ref id, `expected` is
  expected literal, `observed` is observed literal.
- `reference_misrewrite`: observed literal differs from both original and
  expected, `subject` is ref id, `expected` is expected literal, `observed` is
  observed literal.
- Missing observed entries are treated as observed equal to the original value.

Symbol fqn omissions and misrewrites use the same two kinds with `subject`
equal to the original fqn (not a ref id).

## Symbol collision

After computing expected fqns, if two or more distinct original fqns share one
expected fqn, emit one `symbol_collision` per colliding expected target.

When `collision_top_level_only` is true in the canon, only symbols from
top-level units (not nested archives) participate in collision aggregation.
Nested symbols are ignored for `symbol_collision` even when cascade is on.

Normative `symbol_collision` encoding (do not invent alternatives):

- `subject` is the shared expected fqn (the collision target) in dotted form.
- `expected` is the colliding original fqns, lexicographically sorted, joined
  with commas and no spaces. Worked example for originals `com.foo.Twin` and
  `com.bar.Twin` both relocating to `shaded.Same.Twin`:
  `expected` is `com.bar.Twin,com.foo.Twin` (never `unique`, never a count,
  never unsorted, never space-separated).
- `observed` is always `""`.
- `rule_id` is exactly `reloc.symbol_collision` (never the bare string
  `symbol_collision`).

When `collision_top_level_only` is true, nested-only collisions must not emit
`symbol_collision` even when two nested originals share one expected fqn.

## Cross-root isolation

When `forbid_cross_root_merge` is true, group relocated symbol packages
(package of expected fqn) by unit `root`. If the same relocated package is
produced by two or more distinct roots, emit `isolation_breach`. Nested symbols
participate when cascade is enabled.

Normative `isolation_breach` encoding (do not invent alternatives):

- `subject` is the shared relocated package in **dotted** form — the package
  portion of the expected fqn (everything before the final `.` segment), for
  example `shaded.shared`. Never convert that package to slash form. Slash
  form such as `shaded/shared` is incorrect for this field (slash form is used
  by `namespace_drift`, not by `isolation_breach`). Example: for package
  `shaded.shared`, `subject` is `shaded.shared` (never `shaded/shared`).
- `expected` is every contributing root id, lexicographically sorted, joined
  with commas and no spaces. Worked example for roots `root-a` and `root-b`:
  `expected` is `root-a,root-b` (never only the first root, never unsorted).
- `observed` is always `""`.
- `rule_id` is exactly `reloc.isolation_breach`.

## Stale mappings

A mapping is stale when its `from_prefix` is not a prefix of any symbol fqn,
ref literal, or resource content_ref in the batch (nested unit fields
included). Emit `stale_mapping` with `subject` equal to `from_prefix`,
`expected` and `observed` empty. Stale checks always run, including when a
`relocation_loop` is also present for the same mapping set.

## Shadowed mappings

When `detect_shadowed_mappings` is true, emit `shadowed_mapping` for mapping M
when both hold:

1. There exists another mapping N whose `from_prefix` has M.`from_prefix` as a
   strict package prefix (`N == M + "." + rest` using dotted form).
2. Across every collected name (symbols, refs, resource content refs, including
   nested), longest-prefix selection never chooses M.

Normative encoding: `subject` is M.`from_prefix`, `expected` is the
lexicographically smallest shadowing N.`from_prefix`, `observed` is `""`.
Shadowed is distinct from stale: a shadowed mapping still prefixes at least one
name, but a longer mapping always wins.

## Nested cascade

When `cascade_nested` is true, nested unit arrays are evaluated recursively
with the same active mappings and the parent unit root. When
`cascade_nested` is false, ignore nested arrays for transform and findings
other than stale mapping scans (stale scans still see nested names).

Emit `cascade_gap` when `cascade_nested` is true, a nested symbol or ref would
change under relocate, and `observed.nested_applied` is false. `subject` is
the parent unit path, `expected` is `true`, `observed` is `false`.

Emit `nested_omission` when cascade is required and an observed nested ref or
symbol (listed under `observed.nested` keyed by unit path) shows omission as
defined above. `subject` is `parent_path#ref_or_fqn`.

Exclusive precedence: when `cascade_gap_suppresses_nested` is true and a
`cascade_gap` is emitted for parent path P, do not also emit `nested_omission`,
`reference_omission`, or `reference_misrewrite` whose `subject` starts with
`P#`. Those nested transform findings are suppressed under the gap.

Orphan residual observations are not suppressed. When
`cascade_gap_suppresses_nested` is true and a `cascade_gap` exists for parent
path P, scan **every** `observed.nested` entry whose `unit_path` equals P
independently:

- An entry contributes a payload signal when `orphan_requires_payload` is true
  and it has at least one symbol or ref.
- Empty shells never contribute.
- Emit **at most one** `orphan_nested_observation` for P if any entry contributed
  a payload signal (two payload entries still yield one finding).
- If every entry for P is an empty shell, emit **no** orphan for P even though
  `cascade_gap` was emitted.

Normative encoding (exact strings — do not invent synonyms):
- `kind` is `orphan_nested_observation`
- `subject` is P
- `expected` is the empty string `""`
- `observed` is the literal string `present` (never `residual`, never
  `true`/`false`, never empty)
- `rule_id` is `reloc.orphan_nested_observation`

Abstract examples (derive from inputs; do not hard-code outcomes): a parent with
payload plus empty shell plus a duplicate payload → one orphan with `observed`
equal to `present`; a parent with only an empty shell under gap → `cascade_gap`
without orphan.

## Resource rewrites

When `check_resource_rewrites` is true, each unit resource `content_ref` is
relocated like a ref. Locate the observed resource by scanning
`observed.resources` for an entry whose `path` equals the input path, else
whose `path` equals the relocated slash path of the input path. Missing entries
are treated as observed content equal to the original content_ref.

Omission and misrewrite use kinds `reference_omission` and
`reference_misrewrite` with `subject` equal to `res:` plus the input resource
path (and `parent_path#res:` plus path when nested). Nested resource checks
obey the same cascade gap suppression rule.

## Dangling observations

When `detect_dangling_observations` is true, scan `observed.symbols`. For each
entry whose `original` is not equal to any unit symbol `fqn` in the batch
(top-level and nested units included), emit `dangling_observation` with
`subject` equal to that `original`, `expected` equal to `""`, `observed` equal
to the entry's `fqn`, and `rule_id` `reloc.dangling_observation`.

Also scan `observed.refs`. For each entry whose `id` is not equal to any unit
ref `id` in the batch (top-level and nested included), emit
`dangling_observation` with `subject` equal to `ref:` plus the unknown id,
`expected` equal to `""`, `observed` equal to the entry's `literal`, and
`rule_id` `reloc.dangling_observation`. Example subject form for an unknown ref
id `ghost-r`: `ref:ghost-r`.

When `detect_dangling_nested` is true, also scan each `observed.nested` block.
For every observed nested symbol whose `original` is not equal to any symbol
`fqn` under the matching parent unit's nested archives (the unit whose `path`
equals `unit_path`, walking that unit's `nested` arrays), emit
`dangling_observation` with `subject` equal to `unit_path + "#" + original`,
`expected` `""`, `observed` the observed nested `fqn`. Example subject form:
`lib/core.jar#com.ghost.Nested`.

## Identity and metadata

When batch `preserve_identity` is true, if observed identity `group` or
`artifact` differs from input identity, emit `identity_loss` with `subject`
`group` or `artifact`, `expected` the input value, `observed` the observed
value.

When canon `preserve_identity_version` is true and batch `preserve_identity` is
true, also require identity `version` to match. On mismatch emit `identity_loss`
with `subject` `version`, `expected` the input version, `observed` the observed
version. When `preserve_identity_version` is false, version may differ freely.

When canon `relocator_epoch_must_equal` is true, emit `metadata_inconsistency`
when `observed.metadata.relocator_epoch` is not exactly equal to
`required_relocator_epoch` (greater or lesser both fail). When the flag is
false, emit only when the observed epoch is less than required. `subject` is
`relocator_epoch`, `expected` is the required epoch as a decimal string,
`observed` is the observed epoch as a decimal string.

## Rollback steps

Sort `steps` by `seq` ascending.

When `digest_bind_resources` is true, the digest seed is
`sha256_hex(batch_id + "|" + join(sorted original symbol fqns including nested, ",") + "|res|" + join(sorted original resource content_refs including nested, ","))`.
When there are no resources the segment after `|res|` is empty, so the seed
still contains the literal `|res|` marker. Collect content_refs from every unit
resource (nested included). When `digest_bind_resources` is false, omit the
`|res|...` segment entirely:
`sha256_hex(batch_id + "|" + join(sorted symbol fqns, ","))`.

Let `map_bind` be computed as follows when `digest_bind_active_maps` is true:

- Always start from the **full batch mapping list** (never a replay subset).
- When `digest_bind_effective_maps` is true, keep only mappings that are
  neither `stale_mapping` nor `shadowed_mapping` under that full list and the
  batch's collected names.
- When `digest_exclude_cycle_maps` is true, also drop any mapping whose
  `from_prefix` appears as a node on a `relocation_loop` cycle for the full
  mapping list (even if that mapping is used and not stale). If cycle nodes are
  `com.a` and `com.b`, both are excluded from `map_bind` even when `com.a`
  prefixes a used symbol such as `com.a.Thing`.
- When canon `digest_map_bind_order_seq` is true, join surviving `from_prefix`
  values in ascending mapping `seq` order (NOT lexicographic order). Example:
  effective prefixes `com.foo` (seq 1) then `com.bar` (seq 2) yield
  `map_bind` `com.foo,com.bar` — never `com.bar,com.foo`.
- When `digest_map_bind_order_seq` is false, sort those prefixes lexicographically
  before joining.
- If every mapping is excluded, `map_bind` is the empty string (the `|maps|`
  marker is still appended on successful applies). When all mappings are stale,
  successful applies still hash
  `sha256_hex(digest + "|ok|" + seq + "|maps|" + "")`.
- When `digest_bind_effective_maps` is false and `digest_map_bind_order_seq` is
  true, join every mapping `from_prefix` in ascending `seq` order.

Digest simulation for the full batch always uses that full-batch `map_bind`.
Do not recompute `map_bind` from a replay subset.

For each step with `op` equal to `apply`:
- if `fail` is false and `digest_bind_active_maps` is true, set digest to
  `sha256_hex(digest + "|ok|" + strconv(seq) + "|maps|" + map_bind)`;
- if `fail` is false and `digest_bind_active_maps` is false, set digest to
  `sha256_hex(digest + "|ok|" + strconv(seq))`;
- if `fail` is true and `rollback` is true, leave digest unchanged;
- if `fail` is true and `rollback` is false, set digest to
  `sha256_hex(digest + "|fail|" + strconv(seq))` (never append `|maps|` on the
  fail path).

Compare the final simulated digest to `observed.digest`. On mismatch emit
`rollback_incomplete` with `subject` `digest`, `expected` the simulated
digest, `observed` the observed digest.

When `replay_skips_digest` is true, replay subset analysis must omit the
digest/`rollback_incomplete` check entirely (still evaluate loops, stale,
shadowed, collisions, isolation, rewrites, identity, metadata, orphans). The
full-batch evaluation still performs the digest check. Therefore a replay
subset may pass even when the full batch emits `rollback_incomplete`.

## Replay schedules

When `replay.schedules` is missing or empty: `schedules_run` 0,
`schedules_passed` 0, `stable` true.

Otherwise `schedules_run` is the schedule count. For each schedule, keep only
mappings whose `seq` appears in `mapping_seq_order`, recompute findings for
that subset (including loops, collisions, shadowed, resources, and observed
comparisons). An empty `mapping_seq_order` means the active mapping set is
empty (no remaps). When `replay_ignore_unknown_seqs` is true, seq values that
do not match any batch mapping `seq` are ignored when building the subset and
when measuring schedule length for prefix/full stability checks (they still
remain listed in the raw schedule JSON). A schedule passes when the subset
produces zero findings. `schedules_passed` counts passes. An empty schedule
fails when observed values remain relocated while no mappings are active. A
schedule `[1, 99]` with unknown `99` behaves like `[1]` when the ignore-unknown
flag is true.

### Replay `stable` flag (normative precedence)

Compute `stable` with this precedence (later rules override earlier ones):

1. Default: `stable = (schedules_passed == schedules_run)`.
2. If the full batch has one or more findings AND every schedule's effective
   `mapping_seq_order` length (after dropping unknown seqs) is a strict prefix
   shorter than the full mapping count AND `prefix_stable_on_findings` is true,
   then `stable` MUST be `true`.
3. If the full batch has one or more findings AND every schedule's effective
   length equals the full mapping count AND `full_unstable_on_findings` is
   true, then `stable` MUST be `false` — even when `schedules_passed ==
   schedules_run`.

Abstract example for rule 3: one schedule whose effective order length equals
the full mapping count, the full batch has findings, and
`full_unstable_on_findings` is true. After digest-skipping replay the schedule
may pass (`schedules_passed == schedules_run`), but rule 3 still forces
`stable` to `false`. Do not emit `stable: true` merely because all schedules
passed.

## Per-batch flags

- `mapping_ok`: no `relocation_loop`, `stale_mapping`, `shadowed_mapping`
- `rewrite_ok`: no `reference_omission`, `reference_misrewrite`,
  `namespace_drift`, `nested_omission`, `cascade_gap`,
  `orphan_nested_observation`, `dangling_observation`
- `isolation_ok`: no `symbol_collision`, `isolation_breach`
- `identity_ok`: no `identity_loss`, `metadata_inconsistency`
- `rollback_ok`: no `rollback_incomplete`
- `relocation_ok`: all of the above true and findings empty

## Finding fields

Each finding: `kind`, `subject`, `expected`, `observed`, `rule_id`.
`rule_id` is always exactly `reloc.<kind>` — the literal prefix `reloc.` plus
the kind string. Examples: `reloc.symbol_collision`, `reloc.isolation_breach`,
`reloc.dangling_observation`. Never emit `rule_id` equal to the bare kind.

### Findings array ordering (normative, mandatory)

After collecting every finding for a batch from every check, you MUST:

1. Deduplicate identical `(kind, subject, expected, observed, rule_id)` tuples.
2. Sort the remaining findings with a **single global lexicographic ascending
   sort** on the tuple `(kind, subject, expected, observed)` using ordinary
   UTF-8/byte string order.
3. Empty strings sort before any non-empty string on each compared field.
4. **Do not** sort by `rule_id`. **Do not** keep findings grouped by check
   type / emission phase / insertion order. **Do not** apply a secondary sort
   key outside `(kind, subject, expected, observed)`.

Counter-example: `reference_misrewrite` findings MUST appear before
`shadowed_mapping` because `'r' < 's'`. Emitting `shadowed_mapping` first
(common when grouping mapping checks before rewrite checks) is incorrect even
if every finding body's fields are otherwise right.

### Finding field encodings (normative)

These coordinates are exact. Multi-value strings are always lexicographically
sorted and comma-joined with no spaces. Never use placeholder tokens such as
`unique`, never emit a count, and never leave a multi-value field as only the
first element.

| kind | subject | expected | observed |
|------|---------|----------|----------|
| `relocation_loop` | closed `>` walk starting at lex-smallest node | `""` | `""` |
| `stale_mapping` | `from_prefix` | `""` | `""` |
| `shadowed_mapping` | shadowed `from_prefix` | lex-smallest shadowing `from_prefix` | `""` |
| `symbol_collision` | shared expected fqn | sorted originals joined by `,` | `""` |
| `isolation_breach` | shared relocated package | sorted roots joined by `,` | `""` |
| `namespace_drift` | original fqn | slash form of relocated package | relocated `pkg_path` |
| `reference_omission` | ref id, original fqn, or `res:` path | expected rewritten value | observed value |
| `reference_misrewrite` | ref id, original fqn, or `res:` path | expected rewritten value | observed value |
| `cascade_gap` | parent unit path | `true` | `false` |
| `orphan_nested_observation` | parent unit path | `""` | `present` |
| `dangling_observation` | unknown `original`, `ref:`+id, or `parent#original` | `""` | observed fqn/literal |
| `nested_omission` | `parent_path#ref_or_fqn` | expected rewritten value | observed value |
| `identity_loss` | `group`, `artifact`, or `version` | input value | observed value |
| `metadata_inconsistency` | `relocator_epoch` | required epoch decimal | observed epoch decimal |
| `rollback_incomplete` | `digest` | simulated digest hex | observed digest |
