# Count ledger and count staging

The sampler maintains three integer count structures over the whole corpus:

- `n_dk[d][k]`: number of tokens in document `d` currently assigned to topic `k`.
- `n_kw[k][w]`: number of occurrences of vocabulary term `w` currently assigned to topic `k`.
- `n_k[k]`: total number of token occurrences currently assigned to topic `k`.

Adding an assignment increments all three of `n_dk[d][k]`, `n_kw[k][w]`, and `n_k[k]`. Removing an assignment decrements all three. The three structures must remain mutually consistent after every add and every remove; in particular, at any point `n_k[k]` equals the sum over `w` of `n_kw[k][w]` and equals the sum over `d` of `n_dk[d][k]`, and the sum over `k` of `n_k[k]` equals the total number of token occurrences in the corpus.

`ldactl sample` writes `/app/state/lda-count-staging.json` with schema `lda-counts/v1` and these members: `k`, `alpha`, `beta`, `seed`, `sweeps`, `burn_in`, `retained_sweeps` (see `burn-in.md`), `vocab` and `doc_ids` copied from the corpus snapshot in the same order, `assignments` (one array of final topic ids per document, in canonical token order), `n_dk`, `n_kw`, `n_k`, and `theta_sum` (see `burn-in.md`). All counts are the final counts after the last sweep.
