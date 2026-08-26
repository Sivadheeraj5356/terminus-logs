# Output schema

Each subcommand prints exactly one JSON object to stdout. Keys are exactly as
written, no extras and none missing.

## `acl evaluate`

    {
      "decisions": [
        {
          "src": "10.1.2.3",
          "dst": "192.168.1.10",
          "port": 22,
          "protocol": "tcp",
          "direction": "inbound",
          "decision": "allow",
          "matched": "allow-ssh",
          "logged": ["log-ssh"]
        }
      ],
      "summary": {"allow": 5, "deny": 3, "flagged": 3, "total": 8}
    }

- `decisions` lists one object per flow, in the same order as the input flows. Do
  not sort or dedupe them.
- Each decision object has exactly these eight keys: `src`, `dst`, `port`,
  `protocol`, `direction`, `decision`, `matched`, `logged`.
- `src`, `dst`, `port`, `protocol`, `direction` echo the flow as read. `port` is
  an integer.
- `decision` is the string `allow` or `deny`, exactly. Never `log`, never a
  boolean, never capitalized. A log rule is never a decision.
- `matched` is a string: the id of the terminal rule that decided the flow, or
  the sentinel `default-deny` when nothing matched and the flow was denied by
  default. It is the sentinel string, never null, never empty, never a rule
  index.
- `logged` is an array of strings: the ids of the log rules crossed before the
  decision, in evaluation order. It is always an array, `[]` when no log rule was
  crossed, never null. A default-denied flow can still have a non-empty `logged`.
- `summary` has exactly four integer keys: `allow` (decisions that came out
  allow), `deny` (decisions that came out deny), `flagged` (decisions whose
  `logged` array is non-empty), and `total` (number of decisions).
  `allow + deny == total`. `flagged` is independent and can overlap either.
- The top-level object has exactly the two keys `decisions` and `summary`.

## `acl lint`

    {
      "warnings": [
        {"index": 8, "code": "normalized", "detail": "10.0.0.0/8"}
      ],
      "by_reason": {"normalized": 1},
      "shadowed": [{"index": 4, "detail": "3"}],
      "redundant": [{"index": 5, "detail": "0"}],
      "unreachable": [{"index": 7, "detail": ""}],
      "summary": {"rules": 9, "reachable": 6, "shadowed": 1, "redundant": 1,
                  "unreachable": 1, "dropped": 0}
    }

The lint report is where the cross-phase signals surface. The load-step notes
(`warnings`/`by_reason`) and the analysis-step findings
(`shadowed`/`redundant`/`unreachable`) all have to reach it. The top-level object
has exactly these six keys.

- `warnings` is the load-phase log: one object `{"index": <int>, "code": <str>,
  "detail": <str>}` per warning recorded while loading (the reason codes in
  `ruleset-format.md`, including the informational `normalized`). A single rule
  can contribute several entries on the same index. The array is sorted by
  `index` ascending, and entries sharing an index are ordered by `code`
  ascending. It is always an array, `[]` when the ruleset loaded clean.
- `by_reason` is an object tallying the `warnings` by their `code`: each key is a
  code that occurred and its value is how many `warnings` entries carry it. Codes
  that did not occur are absent, so an empty object `{}` means no warnings. The
  values are integers and sum to the length of `warnings`.
- `shadowed`, `redundant`, `unreachable` are the analysis findings, each an array
  of `{"index": <int>, "detail": <str>}` sorted by `index` ascending, always an
  array. `shadowed` detail is the covering rule's file index as a string;
  `redundant` detail is the earlier identical rule's file index as a string;
  `unreachable` detail is the empty string. A rule appears in at most one of the
  three (the precedence in `evaluation.md`).
- `summary` has exactly six integer keys. `rules` is how many rules loaded (the
  dropped ones are not counted). `shadowed`, `redundant`, `unreachable` are the
  lengths of the matching arrays. `reachable` is the loaded rules that are none of
  those three, so `reachable + shadowed + redundant + unreachable == rules`.
  `dropped` is how many rule objects in the file were dropped at load, which
  equals the raw rule count minus `rules` and also equals the number of distinct
  indices carrying a non-`normalized` warning.

## Consistency between the two

For the same ruleset and flows, the set of terminal `matched` ids in `evaluate`
(excluding the `default-deny` sentinel) names only rules that `lint` counts as
reachable, and no rule that `lint` flags shadowed, redundant, or unreachable is
ever a terminal `matched` id.
