# Input and output schema

## Input (stdin)

One JSON object:

```json
{
  "counters": 2,
  "rules": [
    {"take": [1, 0], "give": [1, 1]}
  ],
  "start": [1, 0],
  "queries": [[1, 5], [2, 0]]
}
```

- `counters` — integer, `1..12`.
- `rules` — array of at most 16 objects, each with `take` and `give`.
- `start` — the initial counter values.
- `queries` — array of at most 32 query vectors.
- Every vector has exactly `counters` entries, each a JSON integer in
  `0..1000`. Unrecognized extra fields are ignored.

## Output (stdout)

Exactly one JSON object, then a newline.

For a conforming job:

```json
{"covered": [true, false]}
```

- `covered` is always present, one boolean per query, in query order (it is
  `[]` when the job has no queries).

For a non-conforming job:

```json
{"malformed": true}
```
