# Fold digest and seal contracts

Normative SHA-256 recipes for `/app/bin/foldctl assemble`. Digests are lowercase hex over UTF-8. Multi-field bodies join components with `|` (U+007C). Integer fields in hash bodies use base-10 decimal strings unless a formula says otherwise.

- `fold_digest` is SHA-256 of newline-joined `fold_id|row_count|label_hist` per fold sorted by `fold_id` (`label_hist` is comma-joined `label=count` sorted by label).

- `cohort_checksum` is SHA-256 of newline-joined `id|label` sorted by numeric `id` (unbounded decimal integers, arbitrary precision).

- `assignment_seal` is SHA-256 of newline-joined `label|fold_sequence` sorted by label (`fold_sequence` is comma-joined fold ids in `id` order within the label).

- `balance_anchor` is SHA-256 of `fold_digest|max_label_skew` with six-decimal formatting only in that hash input; the JSON `balance.max_label_skew` keeps full R precision.

- `manifest_seal` is SHA-256 of `cohort_checksum|assignment_seal|balance_anchor|fold_count`.

- `staged_fingerprint` hashes staged CSV bytes.

- `quorum_witness` is SHA-256 of newline-joined `label|min_fold_id` sorted by label.

- `stratum_spread_digest` is SHA-256 of newline-joined `label|spread` sorted by label (`spread` = max−min per-label counts across folds, zero when omitted).

- `band_anchor` is SHA-256 of `skew_band|fold_digest`.

- `rotation_epoch` is a monotonic integer in `/app/var/fold_work/rotation_epoch.txt` starting at `1` when absent and incrementing after each successful assemble.

- `receipt_chain` is SHA-256 of `previous_chain|manifest_seal` with `GENESIS` when no prior receipt exists.

- `epoch_seal` is SHA-256 of `rotation_epoch|manifest_seal`.

- `ledger_root` is SHA-256 of `staged_fingerprint|cohort_checksum|epoch_seal`.

- `fold_parity_digest` is SHA-256 of newline-joined `fold_id|parity` sorted by `fold_id` (`even`/`odd` from `fold_id % 2`).

- `label_coverage_seal` is SHA-256 of newline-joined `label|fold_coverage` sorted by label (`fold_coverage` = number of folds with a positive count for that label).

- `holdout_fold_id` is `(rotation_epoch - 1) % K`.

- `evaluation_seal` is SHA-256 of `fold_parity_digest|label_coverage_seal|holdout_fold_id|manifest_seal`.

- `stratum_entropy_hint` is SHA-256 of newline-joined `label|entropy_bucket` sorted by label (`sparse` when the label's total row count is strictly less than `K`, otherwise `dense`).

- `assemble_attestation` is SHA-256 of `evaluation_seal|ledger_root|stratum_entropy_hint`.

- `fold_load_skew` is `max(row_ids.size()) - min(row_ids.size())` across folds, or `0` when there are no folds.

- `label_cardinality` is the count of distinct labels across all fold `label_counts` key sets, or `0` when empty.

- `cohort_span_digest` is SHA-256 hex (lowercase) of unique labels sorted lexicographically and joined by newline, or the hash of the empty string when there are no labels; `label_cardinality` must equal the number of labels in that body.

- `balance_coupler` is SHA-256 of `balance_anchor|band_anchor|skew_band`.

- `kit_closure` is SHA-256 of `assemble_attestation|fold_load_skew|label_cardinality|cohort_span_digest|balance_coupler` with integers as base-10.

- `run_chain_digest` is SHA-256 of `previous_run_chain|kit_closure` where `previous_run_chain` is the last receipt's `run_chain_digest` or `GENESIS`.

- `class_prior_seal` sums each label's count across every fold's `label_counts`, divides by `row_count` to get that label's prior, formats it to six decimals, and hashes the newline-joined `label|prior` lines sorted by label ascending; with no labels or a non-positive `row_count` it hashes the empty string.

- `fold_split_witness` hashes newline-joined `fold_id|first_id|last_id|size` lines sorted by `fold_id`, where `first_id`/`last_id` are the minimum and maximum numeric row id in that fold written as decimal strings and `size` is that fold's row count; an empty fold contributes `fold_id|-|-|0`, and no folds at all hashes the empty string.

- `holdout_epoch_coupler` is SHA-256 of `holdout_fold_id|rotation_epoch|fold_count|evaluation_seal` with the integers in base ten, binding the current holdout choice to the live evaluation seal and epoch.

- `stratum_stability_index` looks at every fold with at least one row, computes each label's share as its count in that fold divided by that fold's size, takes the highest and lowest share seen for the label across those folds (six-decimal formatting), and hashes newline-joined `label|max_share|min_share` lines sorted by label; when every fold is empty it hashes the empty string, and with a single contributing fold `max_share` equals `min_share`.

- `train_fold_mask` is SHA-256 of the comma-joined sorted train fold ids (every `fold_id` present in the fold records except `holdout_fold_id`); when no train folds remain it hashes the empty string.

- `label_pair_cooccurrence` walks folds sorted by `fold_id` and, for every unordered label pair `(a,b)` with `a < b` lexicographically where both labels have positive counts in that fold, emits `fold_id|a|b`; the SHA-256 is over those lines joined by newline, or the empty string when there are no such pairs.

- `balance_drift_witness` recomputes Java max label skew the same way R does (for each label and each non-empty fold, `abs(fold_share - global_share)`, taking the max; empty folds skipped; `0.0` when there are no positive folds or `row_count <= 0`), formats both that Java skew and R's `max_label_skew` with Locale.US `%.6f`, and hashes `javaSkewSix|rSkewSix|skew_band`.

- `epoch_manifest_binder` is SHA-256 of `rotation_epoch|fold_digest|class_prior_seal` with the epoch in base ten.

- `holdout_exclusion_seal` is SHA-256 of `train_fold_mask|holdout_fold_id|fold_load_skew`.

- `fold_kit_seal` is SHA-256 of `kit_closure|class_prior_seal|fold_split_witness|holdout_epoch_coupler|stratum_stability_index|train_fold_mask|label_pair_cooccurrence|balance_drift_witness|epoch_manifest_binder|holdout_exclusion_seal`, so it only changes when the assignment, the balance chain, or the current rotation epoch changes.

- `fold_coverage_lattice` is SHA-256 of `label_coverage_seal|fold_parity_digest|stratum_stability_index|label_cardinality` with the cardinality in base ten.

- `holdout_train_tension` is SHA-256 of `train_fold_mask|holdout_exclusion_seal|holdout_epoch_coupler|fold_load_skew`.

- `skew_prior_witness` is SHA-256 of `balance_drift_witness|class_prior_seal|balance_coupler|{max_label_skew}` where `max_label_skew` is R's value formatted Locale.US `%.6f`.

- `epoch_receipt_binder` is SHA-256 of `epoch_manifest_binder|run_chain_digest|receipt_chain|rotation_epoch`.

- `fold_kit_outer_seal` is SHA-256 of `fold_kit_seal|fold_coverage_lattice|holdout_train_tension|skew_prior_witness|epoch_receipt_binder`.

## JSONL receipt (`/app/var/fold_receipt.jsonl`)

Each successful assemble appends one JSON object (one line). Values must match the assemble stdout/manifest for that run. Required keys:

`row_count`, `fold_count`, `label_column`, `manifest_seal`, `fold_digest`, `receipt_chain`, `rotation_epoch`, `ledger_root`, `evaluation_seal`, `assemble_attestation`, `holdout_fold_id`, `kit_closure`, `run_chain_digest`, `fold_load_skew`, `label_cardinality`, `balance_coupler`, `cohort_span_digest`, `class_prior_seal`, `fold_split_witness`, `holdout_epoch_coupler`, `stratum_stability_index`, `train_fold_mask`, `label_pair_cooccurrence`, `balance_drift_witness`, `epoch_manifest_binder`, `holdout_exclusion_seal`, `fold_kit_seal`, `fold_coverage_lattice`, `holdout_train_tension`, `skew_prior_witness`, `epoch_receipt_binder`, `fold_kit_outer_seal`.
