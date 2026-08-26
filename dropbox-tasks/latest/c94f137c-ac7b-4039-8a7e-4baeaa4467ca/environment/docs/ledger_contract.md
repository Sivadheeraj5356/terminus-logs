# Ledger settlement

Settlement walks frames in global read order after CRC validation and epoch filtering. Global order comes from sorted *.cdk basenames, then ascending frame sequence within each file.

## Region gate

When region_gate is true in configs/audit_profile.json, only upsert and transfer rows whose region appears in data/region_codes.txt count toward record_count and distinct_account_count. Rejected rows still enter the digest chain.

## Supersede

An upsert or transfer may carry replaces_seq. When present, the prior active row for the same account at that sequence slot is retired before the replacement is recorded. Both the retired and replacement rows stay in the digest walk.

## Tombstone

A tombstone removes every active upsert or transfer row for the named account from settlement totals. Tombstones hash with a slim canonical JSON (account, kind, region, seq only) and do not increment retract_count.

## Void

A void increments retract_count only. Void rows still participate in the digest walk with the full payload canonical form.

## Duplicate slot

When two upsert or transfer rows in the kept stream share the same account and payload seq, settlement keeps the last row and increments duplicate_slot_drops. Both rows remain in the digest walk.
