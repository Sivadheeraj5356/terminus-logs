# Trace snapshots

These three fixtures are captured fragment streams, one per daylight-saving
window. The step tool replays them so a rebuild can be reproduced offline.

- `backward.rows` covers an autumn fall-back weekend, where the local clock
  repeats an hour and the same calendar day is recorded twice.
- `forward.rows` covers a spring forward weekend, where one civil hour is
  skipped and never lands on the local wall clock.
- `resume.rows` covers a host that came back after maintenance. The first
  fragment is a timezone-skip (flag 0x04). The second fragment has a boot-gap
  wall_offset (at or above 86400). On the initial rebuild that second fragment
  is still first-pass work with seq below 100; it is not a recovery row.

Packed output built from these snapshots is expected to satisfy the contract
described in `docs/ledger_format.md`.
