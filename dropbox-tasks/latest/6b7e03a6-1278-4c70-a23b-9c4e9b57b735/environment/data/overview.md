# Online shopper purchase-intent under a seasonal shift

Each row is one e-commerce browsing session described by ten numeric
engagement features and six categorical context features. The binary
`target` marks whether the session ended in a purchase.

The `domain` column splits the sessions into two regimes. `source`
sessions come from the off-season part of the year and are all labeled.
`target` sessions come from the peak shopping season; only a small
labeled pilot is provided and the rest have a blank `target` and must be
scored. Purchase behaviour differs between the two regimes.

See `split_note.md`, `pilot_note.md`, `codebook.csv` and the summary
files for column descriptions and the split design.
