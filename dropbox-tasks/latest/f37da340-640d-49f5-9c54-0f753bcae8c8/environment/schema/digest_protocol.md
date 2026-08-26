# Durable digest protocol

`durable_digest` is a lowercase hex digest of the newline-joined, sorted
canonical lines built from the durable store snapshot.

Line tokens (one per line, then sort the full line list):

```
entry:<arm>:<order_key>:<opts>
cref:<arm>:<epoch>
refresh:<count>
barrier:<barrier_rev>
run:<run_id>
seq:<journal_seq>
steps:<step_count>
```

For `entry` lines, prefer durable-store opts after a barrier has committed
pending reconcile; otherwise use the compiled entry opts. The site tool hashes
the UTF-8 payload formed by joining the sorted lines with newlines (no trailing
newline after the last line before hashing) via `/usr/lib/sitefab/law_digest.py`.

When Digestion Source is not the durable store path, the appliance emits a
separate health-cache digest that is not interchangeable with the durable form.
