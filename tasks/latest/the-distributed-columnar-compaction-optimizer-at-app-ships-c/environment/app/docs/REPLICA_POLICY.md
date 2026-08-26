# Replica mask policy

Each fragment carries replica_mask as a bitset of available replicas.

## Consistency rule

replica_consistent is true when every fragment in the catalog satisfies:

```
(fragment.replica_mask & policy.required_replica_mask) == policy.required_replica_mask
```

When any fragment lacks a required replica bit, replica_consistent must be false and validation reports REPLICA_MISMATCH if the plan claims consistency.

Default policy required_replica_mask is 0x0007 (bits 0, 1, 2). Sample tier definitions live in /app/data/configs/replica_tiers.json.
