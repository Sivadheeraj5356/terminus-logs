# Cryptographic witness-MAC custody wire layout

Each custody segment carries `id`, `base_seq`, `offset_min`, and an `events`
array used for anti-tamper forensic attestation. Event rows use 1-based `seq`,
unix `sec`, `nsec`, and a forensic `action` token. Those fields fold into the
tamper-evident custody-head digest that authenticates the incident timeline.
Broken seals or skewed forensic order are expected to surface as non-intact
chain counters rather than silently passing.

Local segment clocks map onto a shared UTC custody timeline by combining
seconds and nanoseconds, then subtracting the segment's `offset_min` (converted
to nanoseconds). That subtractive normalization is what lets cross-zone
evidence share one authenticated forensic clock. Without it, the same incident
can look reordered solely because two collectors were sitting in different
zones. Custody merge steps name `left` and `right` segment ids. After a merge
the right segment inherits a rebased sequence window taken from the surviving
senior base plus the left segment's event width, and the surviving senior
witness anchor propagates for later forensic ordering when the left base is not
greater than the right base.

Forensic replay keeps equal-wall ties stable using the propagated witness
anchor together with segment and effective-sequence coordinates, in that field
order. Witness `contradiction_count` tallies effective-sequence inversions with
an O(n²) all-pairs scan over every pair of events that share the same wall
time — not an adjacent-pair walk of the replay order. Getting either of those
wrong usually shows up as inflated contradiction or order-drift counters even
when the wall clock itself looks fine.

Local seal construction forms seal material as the decimal active session
epoch, a single colon, and the lowercase hex digest of the forensic-order
action stream. Actions are joined with `|` in forensic order, not lexicographic
order. The local seal itself is the lowercase hex of SHA-256 over that material
string — not the raw `epoch:mixhex` material. The active session epoch is the
scenario `session_epoch` plus the sum of every `epoch_bump` in
`/app/config/rotate_schedule.json` whose `after_events` threshold is less than
or equal to the pack's cumulative `events_replayed` from earlier scenarios
only.

Pack-order head binding folds the previous scenario's `timeline_head_hex` (or
the schedule's `genesis_prior` for the first row) with that local seal digest:
lowercase hex of SHA-256 over `prior + ":" + local_seal`. Isolated
`chronctl -pack <path> -probe <name>` must replay the pack prefix through the
named scenario so the probe row matches the full report, including rotate bumps
and prior-head binding. Isolated witness inspection prints one attestation row
as JSON on stdout.
