# Snapper timeline precedence (ops notes)

## Checkpoint reuse

Warm replay may skip rebuilding a scenario when `/app/svc-state/checkpoint/epoch.json` matches the bound ledger snapshot on **ledger epoch**, **material generation**, and **handoff generation** together, and the material file already exists. A stamp that only matches generation is not sufficient after handoff drift.

## Replay order

Profiles replay in `/app/environment/config/replay_order.tsv` order, not catalog file order. `clock_step` precedes `journal_batch` in the shipped order.

## Handoff journal

`/app/state/handoff/journal.json` carries `anchor_epoch` and `stepback_latched` across the replay walk. After each profile, the journal updates before the next profile materializes.

Stepback latch arms from trace `stepback_event` (not `clock_skew`) when an NTP step-back profile replays. Retention stride recycle on later profiles observes `stepback_latched`, not merely a positive `anchor_epoch`.

## WAL journal batches

WAL segments merge by segment `seq`. Filename order (`file_name`) is misleading; see `logs/wal_dir_listing.txt`. The last non-empty override in sequence order wins.

## Timeline label collisions

When label text ties, keep the row with the **greater** label `epoch`. Ledger `anchor_epoch` is not a substitute for label epoch on ties.

## Locale catalog lists

C-locale samples use semicolon-separated fields per line (`logs/list_c_locale.txt`). Host samples use whitespace. The newest numeric id across **all** fields on each line wins.

## Retention recycle

When `retention_epoch >= sweep_epoch` from `/app/environment/config/resume_policy.toml` **and** handoff journal `stepback_latched` is 1, subtract `stride` from each automation id at or above `stride` independently.

## Mount visibility

`scope_visible` is 1 only when at least `quorum_min` views from `/app/environment/config/view_policy.toml` match the target path.
