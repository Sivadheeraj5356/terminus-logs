# Operator notes

The default input root is `/app/environment/data/cell_bin`. Production callers
write to a path on the same filesystem so the final rename is atomic.
Unsuccessful invocations must leave the previously published attestation
untouched.

Raw source commitments are expected to change after harmless sharding or file
renames. Downstream comparisons should separate those byte commitments from
the semantic observations, models, replays, and lineage records.
