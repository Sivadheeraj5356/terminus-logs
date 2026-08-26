# Admissible source recoveries

The candidate universe is the Cartesian product of every tone and every source in the
campaign. Candidate identity is the string `tone_id + "@" + source_id`. Canonical
candidate order is ascending `(tone_id, source_id)` by bytewise ASCII comparison.

A support is a subset of candidates with size at most `max_active_sources`. Each chosen
candidate owns two unknown exact coordinates, `cos` and `sin`. Apply trigger rotation,
the candidate's source/probe path, folding, and collision addition to those unknowns.
For every capture, probe, bin, and coordinate, the resulting value must equal
`measured - expected`.

A support is admissible only when all of these conditions hold:

1. the complete coordinate system has exactly one rational solution for that support;
2. every chosen candidate has at least one nonzero source coordinate;
3. substituting the solved coordinates reproduces every residual coordinate exactly.

A rank-deficient support is not admissible even if it has fitting solutions. The empty
support is admissible precisely when every residual coordinate is zero; its solution,
rank, and unknown count are all zero.

Choose the admissible support by this total order:

1. smaller support size;
2. lexicographically smaller sorted list of candidate identities.

No amplitude, energy, tone rate, or input-file order participates in the tie. This
priority pins one recovery even when two different supports each have a unique exact
fit.

If no admissible support exists within the campaign limit, the campaign has no recovery.
That condition is a failed invocation: the destination is not created, removed, or
replaced.
