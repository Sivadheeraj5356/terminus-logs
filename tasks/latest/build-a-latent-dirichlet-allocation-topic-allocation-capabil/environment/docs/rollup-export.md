# Rollup export

`ldactl export` reads only the corpus staging and count staging snapshots and writes `/app/output/lda-topic-rollup.json` with schema `lda-rollup/v1` and these members:

- `retained_sweeps`: copied from the count snapshot.
- `topics`: one entry per topic in ascending topic order `0..K`. Each entry has `topic` (the topic index) and `top_terms` (see `topic-ranking.md`).
- `documents`: one entry per document in ascending `doc_id` order, matching the count snapshot's `doc_ids`. Each entry has `doc_id` and `theta`, a length-`K` distribution.
- `snapshot_checksum`: see below.

The per-document distribution is `theta[k] = theta_sum[d][k] / retained_sweeps`, followed by normalizing the row so its entries sum to one (the row already sums to approximately one, so normalization only removes rounding drift).

Before writing, `export` validates that the two snapshots agree: the `vocab` lists must be identical, the corpus document order must equal the count snapshot `doc_ids`, the topic count must match the configuration, and the count arrays must have consistent shapes. If any check fails, `export` exits nonzero and leaves any existing output file untouched.

The checksum is the lowercase hexadecimal SHA-256 of the exact corpus-staging bytes, followed by the separator bytes `\n--counts--\n`, followed by the exact count-staging bytes, in that order.
