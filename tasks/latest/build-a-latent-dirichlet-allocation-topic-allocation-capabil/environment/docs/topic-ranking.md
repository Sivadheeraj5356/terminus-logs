# Topic term ranking

Each topic's top terms are ranked by the smoothed posterior term probability computed from the final counts in the count staging snapshot. For topic `k` and vocabulary term `w` with size `V`:

    probability(k, w) = (n_kw[k][w] + beta) / (n_k[k] + V * beta)

Rank the vocabulary terms for a topic by `probability` in descending order. Break ties (equal probability) by the token string in ascending lexicographic order. Keep the first `top_terms` entries, where `top_terms` comes from the configuration. Each retained entry records the token string and its `probability` as a double.

Ranking uses smoothed probabilities, not raw counts, and ties are broken by ascending token order. The reported `probability` is the smoothed posterior value above, not a raw count or an unsmoothed frequency.
