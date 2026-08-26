# Route board

Observed outcome classes for composed route plans:

| Class | Meaning |
| --- | --- |
| hit | Route-want cell reached its published target under first-match ordering |
| deny | Deny-want cell stayed unrouted; target and group are empty strings |
| miss | Cell covered by no emitted row |

Coverage and ordering:

- A row covers a cell only when the row `Kind` equals the cell `kind` and the cell `match`
  appears **verbatim** in the row's `Match` array. Path matchers are exact tokens at audit
  time — `/only` never covers `/only/sub`; prefix expansion happens in the running proxy,
  not in the audit plan.
- Outcomes follow first-match ordering over `rule_rows`: the first covering row decides the
  cell. Never-mode rows are emitted **before** always-mode rows so deny cells are decided
  ahead of any broad always row.
- Each deny-want cell emits its own never-mode row carrying exactly its one matcher, with
  empty `Target`, `Group`, and `Key`. Deny cells must not be dropped from the plan — a
  dropped deny cell reads `miss` instead of `deny`.

Packing and groups:

- Ceiling-aware packing folds all route-want cells that share the same `kind` and published
  `target` into one always-mode row whose `Match` lists every covered matcher, sorted.
- Never rows are ordered by kind then matcher; always rows by kind then target.
- Every always-mode row carries a group key shared by exactly the cells of its
  `kind` + `target` pair: the mapping from (kind, target) pairs to group keys is one-to-one
  across the arm. Distinct group keys are bounded by the published `group_cap`; emitted rows
  by `row_cap`. A plan over either ceiling is a hard error, not a truncation.
- Host-kind and path-kind route cells that publish different targets never share a group key,
  and their published target sets stay disjoint on mixed packs.

Scratch surfaces:

- `/app/var/qxhub/lane.shadow` is a diagnostic scratch hint. The fold step never reads it;
  a plan must not admit rows from shadow hints, whatever an earlier arm left behind.
