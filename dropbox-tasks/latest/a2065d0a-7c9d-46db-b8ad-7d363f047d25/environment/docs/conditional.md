# Collapsed-Gibbs conditional

After initialization the sampler runs `sweeps` full passes over the corpus. Within every sweep, documents are visited ascending by `doc_id` and, within each document, token positions ascending.

For the token occurrence with vocabulary id `w` in document `d`, currently assigned topic `t`:

1. Remove the current assignment from the ledger (decrement `n_dk[d][t]`, `n_kw[t][w]`, and `n_k[t]`).
2. For every topic `k` in `0..K`, compute an unnormalized mass:

       mass[k] = (n_dk[d][k] + alpha) * (n_kw[k][w] + beta) / (n_k[k] + V * beta)

   where `alpha` and `beta` are the configured Dirichlet hyperparameters and `V` is the vocabulary size. The masses are computed with the current, decremented counts.
3. Let `total` be the sum of `mass[0..K]` accumulated in ascending topic order. Draw one uniform double `u` in [0, 1) and form `draw = u * total`.
4. Select the first topic `k` (scanning ascending, accumulating masses) whose running cumulative sum strictly exceeds `draw`. If floating-point rounding leaves `draw` at or beyond the final cumulative sum, select topic `K - 1`.
5. Record the new topic and add it back to the ledger.

Each reassignment consumes exactly one generator step (the draw of `u`). The denominator uses `V * beta`; it is not `V`, and it is not any per-document total.
