# SPOOLD — Print-Spool Service Supervisor (normative specification)

`spoold` is the operator control tool for a host's **print-spool service** — the
system daemon that administers the machine's print devices and the shared spool
of pending jobs, in the spirit of a classic line-printer daemon (`lpd`/CUPS).
Operators use it to inspect and account for the service: which **printers**
(print devices) are busy or **paused**, what sits in each printer's **spool
queue**, how each user (**owner**) stands against their **per-user page quota**,
and how the service handled device faults. It replays the service's operations
**journal** (a stream of administrative **events**) against the set of declared
printers and reports the resulting service state. This document is the single
source of truth. Every output is graded **byte-for-byte** against the canonical
form defined in §2; there is exactly one correct output per input.

This is a bespoke spool-service model. It resembles an ordinary priority print
queue, but several administrative rules (quota accounting, device pause/resume,
fault handling, fair-share dispatch) are stated deliberately, and the correct
answer follows from the stated rule, not from a conventional print queue. Read
§4–§9 carefully.

---

## 1. Input

A **schedule file** is JSON:

```json
{
  "spool": "S1",
  "printers": ["p1", "p2"],
  "budgets": {"alice": 12},
  "max_faults": 3,
  "events": [ <event>, <event>, ... ]
}
```

- `printers` — the declared printer ids. Every printer starts **idle** and
  **not paused**. A printer id that is not declared here does not exist.
- `budgets` — a map from **owner** id to an integer **page budget**. An owner
  **absent** from this map (or whose owner id never appears) has an **unlimited**
  budget.
- `max_faults` — a positive integer used by §8 (`fault`). If omitted, it is `3`.
- `events` — applied strictly in **array order**. Each event is an object:

| field      | meaning                                                        |
|------------|----------------------------------------------------------------|
| `seq`      | integer timeline position (strictly increasing across the file) |
| `op`       | one of `submit`, `finish`, `hold`, `release`, `cancel`, `pause`, `resume`, `fault` |
| `job`      | job id (string) — present on `submit`, `hold`, `release`, `cancel` |
| `owner`    | owner id (string) — present on `submit`                        |
| `printer`  | printer id (string) — present on `submit`, `finish`, `pause`, `resume`, `fault` |
| `pages`    | integer page count (≥ 1) — present on `submit`                 |
| `priority` | integer priority — present on `submit`                         |

---

## 2. Output format

Every command writes one JSON document to **stdout**, in **canonical form**:
UTF-8, object keys sorted ascending, two-space indentation, and a trailing
newline. This is exactly `json.dumps(obj, indent=2, sort_keys=True) + "\n"`.
`null` is written as `null`. No HTML escaping is applied.

---

## 3. Jobs, printers, owners

A **job** is created by a `submit` (§4.1). It has an immutable `owner`,
`printer`, `priority`, `pages`, and a **submit position** fixed by its `submit`
`seq` (**earlier = smaller seq**). Its `state` is one of `queued`, `held`,
`printing`, `done`, `canceled`, `aborted`; it starts `queued`. `done`,
`canceled`, and `aborted` are **terminal**.

A **printer** prints at most one job at a time. It has a **current** job (or
none) and a **paused** flag. A printer is **available** iff it is not paused and
has no current job.

An **owner**'s **committed** pages are the pages of its jobs that have
**finished** (§4.2). Its **reserved** pages are the pages of its jobs that are
currently `printing`. For an owner with a budget `B`, its **remaining** budget is
`B − committed − reserved`; an owner with an unlimited budget has no limit.

Committed pages are also tracked **per printer**. The pages an owner `o` has
**committed on a printer `p`** is the sum of `pages` over exactly those of `o`'s
jobs that have **finished** (§4.2) while assigned to `p`. This per-printer count
is used only by the §6 dispatch tie-break. It counts **finished** pages only: a
job that is currently `printing`, `queued`, `held`, `canceled`, or `aborted`
contributes nothing to it (only `finish` adds to it, by the finishing job's
`pages`), and it is never decreased. It starts at `0` for every `(owner,
printer)` pair. Because every job is fixed to one printer at `submit`, a job's
pages count toward exactly the one printer it targets.

A job is **affordable** iff its owner is unlimited, or the owner's remaining
budget is **≥** the job's `pages` (equality is affordable).

---

## 4. Events and their outcomes

Applying an event yields exactly one **outcome** string, recorded in the log
(§10). The outcomes are `printing`, `queued`, `held`, `released`, `finished`,
`canceled`, `faulted`, `aborted`, `paused`, `resumed`, `noop`, `rejected`.

### 4.1 submit
A `submit` naming `job`, `owner`, `printer`, `pages`, `priority`:

- If `job`, `owner`, `printer`, `pages`, or `priority` is absent; or `pages` is
  not an integer ≥ 1; or `priority` is not an integer; or `printer` is not a
  declared printer; or a job with this `job` id already exists → `rejected` (no
  job is created).
- Otherwise a new `queued` job is created on `printer`, then that printer is
  **dispatched** (§6). The outcome is the new job's resulting state: `printing`
  if the dispatch selected it, else `queued`. (Dispatch may instead select a
  different job, or none; see §6.) In milestone 2 only, if the new job remains
  `queued` after the dispatch, **preemption** (§7) is then attempted.

### 4.2 finish
A `finish` on `printer`:

- If `printer` is not declared → `rejected`.
- Else if the printer has no current job → `noop`.
- Else the current job becomes `done`; its pages move from the owner's
  **reserved** to **committed**; the printer's current job is cleared; then the
  printer is **dispatched** (§6). The outcome is `finished`.

### 4.3 hold
A `hold` on `job`:

- If `job` is absent or unknown → `rejected`.
- Else if the job is `queued` → it becomes `held` (ineligible for dispatch);
  outcome `held`.
- Else if the job is `held` → `noop`.
- Else (`printing` or terminal) → `rejected`.

### 4.4 release
A `release` on `job`:

- If `job` is absent or unknown → `rejected`.
- Else if the job is `held` → it becomes `queued` (keeping its original submit
  position), then its printer is **dispatched** (§6); in milestone 2 only, if it
  remains `queued`, **preemption** (§7) is then attempted. Outcome `released`.
- Else if the job is `queued` → `noop`.
- Else (`printing` or terminal) → `rejected`.

### 4.5 cancel
A `cancel` on `job`:

- If `job` is absent or unknown → `rejected`.
- Else if the job is terminal (`done`/`canceled`/`aborted`) → `rejected`.
- Else if the job is `queued` or `held` → it becomes `canceled`; outcome
  `canceled`. (No printer is dispatched: removing a waiter frees no printer.)
- Else (`printing`) → its reservation is released, its printer's current job is
  cleared, the job becomes `canceled`, then that printer is **dispatched** (§6).
  Outcome `canceled`.

### 4.6 pause
A `pause` on `printer`:

- If `printer` is not declared → `rejected`.
- Else if the printer is not paused → it becomes paused; outcome `paused`. A
  currently printing job is **not** disturbed and may still `finish`; the printer
  simply dispatches nothing new while paused.
- Else → `noop`.

### 4.7 resume
A `resume` on `printer`:

- If `printer` is not declared → `rejected`.
- Else if the printer is paused → it becomes not paused, then is **dispatched**
  (§6); outcome `resumed`.
- Else → `noop`.

---

## 5. (reserved)

---

## 6. Dispatch

Dispatching a printer `p` proceeds as follows:

- If `p` is not **available** (paused, or already has a current job) → nothing
  happens.
- Otherwise consider the **eligible** jobs of `p`: every job that is `queued`,
  targets `p`, and is **affordable** (§3). A job that is not affordable is
  **skipped**, not blocking — a later, affordable job may be selected even when an
  earlier or higher-priority job is unaffordable.
- If there are no eligible jobs → nothing happens.
- Otherwise select the **one** eligible job that is best under this order:
  1. **highest `priority`** (larger wins); then
  2. **fewest pages the job's owner has already committed on this printer**
     — the per-`(owner, printer)` committed count defined in §3, evaluated at the
     moment of this dispatch (smaller wins); then
  3. **earliest submit position** (smaller `seq` wins).

  Note this tie-break is per **owner-on-this-printer** and counts only
  **finished** pages: it uses neither the owner's global committed total nor its
  reserved (currently-printing) pages, and it can override the `seq` order — a
  later-submitted job whose owner has finished fewer pages on this printer is
  selected ahead of an equal-priority job submitted earlier.
  The selected job becomes `printing`, becomes `p`'s current job, and its pages
  are added to its owner's **reserved** total.

A printer holds exactly one job, so a dispatch fills at most one job. Dispatch is
run precisely at the points named in §4 and §7 (after a `submit`, a `finish`, a
`release`, a `cancel` of a printing job, a `resume`, a `fault`, and after a
preemption). It is **not** run on any other printer as a side effect — freeing an
owner's budget on one printer does not, by itself, dispatch a different printer.

---

## 7. Preemption (milestone 2)

Preemption is attempted only where §4.1 and §4.4 say so: immediately after a
`submit` or a `release` whose job `J` **remained `queued`** after the dispatch.
It is attempted once, for `J` only:

- If `J` is not **affordable** (§3) at this moment (with the current job's
  reservation still counted) → no preemption.
- Let `p` be `J`'s printer. If `p` is paused or has no current job → no
  preemption.
- Let `K` be `p`'s current job. If `J`'s `priority` is **strictly greater** than
  `K`'s → `J` **preempts** `K`: `K`'s reservation is released, `K` becomes
  `queued` (keeping its original submit position), `p`'s current job is cleared, a
  **preemption event** is recorded (§10), and `p` is **dispatched** (§6).
  Otherwise → no preemption.

Only one preemption occurs per triggering event. After the ensuing dispatch the
printer may select `J`, or another eligible job (e.g. a still-higher-priority
waiter), by the §6 order — the recorded preemption event names `J` as `by`
regardless of which job the dispatch ultimately selects.

---

## 8. Faults (milestone 2)

A `fault` on `printer`:

- If `printer` is not declared → `rejected`.
- Else if the printer has no current job → `noop`.
- Else let `K` be the current job. `K`'s **fault count** is incremented and its
  reservation is released, and the printer's current job is cleared. Then:
  - if `K`'s fault count has reached `max_faults` (§1) → `K` becomes `aborted`
    and is recorded as an abort (§10); outcome `aborted`;
  - otherwise `K` becomes `queued` (keeping its original submit position),
    carrying its elevated fault count; outcome `faulted`.
  In either case the printer is then **dispatched** (§6).

---

## 9. Structural verify

`verify` scans the raw events **without replaying** and reports the **first
structural error** as `{"seq","reason"}`, or `ok: true`/`error: null` if none.
Per event the possible reasons are:

- `BAD_OP` — `op` is not one of the eight operations in §1.
- `MISSING_FIELD` — a `submit` missing any of `job`/`owner`/`printer`/`pages`/
  `priority`; a `finish`/`pause`/`resume`/`fault` missing `printer`; or a
  `hold`/`release`/`cancel` missing `job`.
- `BAD_PAGES` — a `submit` whose `pages` is present but is not an integer ≥ 1.

If one event triggers several, report the one highest in precedence
`BAD_OP` > `MISSING_FIELD` > `BAD_PAGES`. Across events the smallest `seq` wins.

---

## 10. Commands

Each command prints canonical JSON (§2). Below, "queue order" means ascending
submit position (submit `seq`).

- `spoold log <schedule>` →
  `{"spool","events":[{"seq","op","job","printer","outcome"}]}` — one row per
  event in order. `job` is the event's job id (or `null`); `printer` is the
  event's printer id (or `null`); `outcome` is the §4/§8 outcome.
- `spoold printers <schedule>` →
  `{"spool","printers":[{"printer","current","paused"}]}` — every declared
  printer, sorted ascending; `current` is its current job id or `null`; `paused`
  is a boolean.
- `spoold queues <schedule>` →
  `{"spool","printers":[{"printer","queue":[{"job","owner","priority","pages","state"}]}]}`
  — only printers with at least one `queued`/`held` job, sorted ascending; each
  `queue` in queue order; `state` is `queued` or `held`.
- `spoold jobs <schedule>` →
  `{"spool","jobs":[{"job","owner","printer","priority","pages","state"}]}` —
  every job, sorted ascending by `job`.
- `spoold owners <schedule>` →
  `{"spool","owners":[{"owner","budget","committed","reserved","remaining"}]}` —
  every owner that has a budget or that owns a job, sorted ascending; `budget`
  and `remaining` are `null` for an unlimited owner.
- `spoold trace <schedule> <n>` — the `printers` shape (§10) after applying only
  the first `n` events, with `n` clamped to `[0, len(events)]`.
- `spoold verify <schedule>` → `{"spool","ok","error"}` (§9).
- `spoold preemptions <schedule>` →
  `{"spool","events":[{"at_seq","printer","victim","by"}],"count"}` — the
  preemption events (§7) in the order they occurred; `at_seq` is the triggering
  event's `seq`, `victim` the preempted job, `by` the triggering job.
- `spoold aborts <schedule>` → `{"spool","aborted":[job,...],"count"}` — the jobs
  aborted by §8, in the order they were aborted.
- `spoold job <schedule> <job>` →
  `{"spool","job","state","printer","owner","priority","pages","faults","outcomes":[{"seq","outcome"}]}`
  — one job's final state, its `faults` count, and `outcomes` = its per-event
  outcomes in order for the events that named it (`submit`/`hold`/`release`/
  `cancel`). For an unknown job id, `state` is `"unknown"`, `printer`/`owner`/
  `priority`/`pages` are `null`, `faults` is `0`, and `outcomes` is empty.

`preemptions`, `aborts`, and `job` are milestone-2 commands. Preemption (§7) and
faults (§8) are **milestone-2 behaviour only**, gated as stated in §4.1, §4.4,
and §8. Milestone-1 schedules contain no `fault` events, and they are
constructed so that **no preemption (§7) is ever triggered** — no `submit` or
`release` ever leaves an affordable job queued on a printer whose current job it
outranks. Consequently the milestone-1 schedules are fully determined by §3–§6
and §9 alone, and every milestone-1 command
(`log`/`printers`/`queues`/`jobs`/`owners`/`trace`/`verify`) produces the same
output whether or not an implementation has yet added the §7 preemption rule.

---

## 11. Example schedules

The directory `/app/data/schedules/` holds sample schedule files and
`/app/data/examples/` holds small labelled ones. They are **inputs only** — no
reference outputs are provided. Replay them with your own build. Each labelled
example's name indicates the situation it covers (e.g. `skip_unaffordable`,
`local_dispatch`, `fair_share`, `release_retains_seq`, `preempt_basic`,
`preempt_selfblock`, `crashloop_abort`).

---

## 12. Worked example (format anchor)

Input schedule `{"spool":"E","printers":["p1"],"budgets":{"poor":3},"events":[
{"seq":1,"op":"submit","job":"big","owner":"poor","printer":"p1","pages":10,"priority":9},
{"seq":2,"op":"submit","job":"small","owner":"rich","printer":"p1","pages":4,"priority":1}]}`.

`big` is submitted; its owner `poor` has budget 3 but the job needs 10, so it is
unaffordable and stays `queued` (dispatch selects nothing). `small` is submitted;
its owner `rich` is unlimited, so it is affordable and — even though it has lower
priority — it is dispatched (the unaffordable `big` is skipped, not blocking).
`spoold printers E` prints:

```json
{
  "printers": [
    {
      "current": "small",
      "paused": false,
      "printer": "p1"
    }
  ],
  "spool": "E"
}
```

and `spoold queues E` prints:

```json
{
  "printers": [
    {
      "printer": "p1",
      "queue": [
        {
          "job": "big",
          "owner": "poor",
          "pages": 10,
          "priority": 9,
          "state": "queued"
        }
      ]
    }
  ],
  "spool": "E"
}
```

---

## 13. Worked example — a preemption (format anchor)

This example is **illustrative only** (it is not one of the graded schedules).
Input schedule `D`:

```json
{ "spool": "D", "printers": ["p1"], "budgets": {}, "events": [
  {"seq":1,"op":"submit","job":"lo","owner":"A","printer":"p1","pages":3,"priority":1},
  {"seq":2,"op":"submit","job":"hi","owner":"B","printer":"p1","pages":3,"priority":9} ] }
```

`lo` is submitted and dispatched (it becomes `printing` on `p1`). `hi` is
submitted; `p1` is busy, so `hi` stays `queued`. Because `hi` is affordable (its
owner `B` is unlimited) and its priority `9` is strictly greater than the current
job `lo`'s `1`, `hi` **preempts** `lo`: `lo` returns to `queued`, and the ensuing
dispatch selects `hi`. `spoold preemptions D` prints:

```json
{
  "count": 1,
  "events": [
    {
      "at_seq": 2,
      "by": "hi",
      "printer": "p1",
      "victim": "lo"
    }
  ],
  "spool": "D"
}
```

and afterwards `p1`'s current job is `hi` while `lo` is `queued` again.

---

## 14. Worked example — the fair-share tie-break (format anchor)

This example is **illustrative only** (it is not one of the graded schedules). It
pins the §6 rule-2 tie-break defined in §3. Input schedule `F` (all owners
unlimited):

```json
{ "spool": "F", "printers": ["p1"], "budgets": {}, "events": [
  {"seq":1,"op":"submit","job":"u1","owner":"A","printer":"p1","pages":1,"priority":5},
  {"seq":2,"op":"finish","printer":"p1"},
  {"seq":3,"op":"submit","job":"hi","owner":"C","printer":"p1","pages":1,"priority":9},
  {"seq":4,"op":"submit","job":"u2","owner":"A","printer":"p1","pages":1,"priority":5},
  {"seq":5,"op":"submit","job":"w1","owner":"B","printer":"p1","pages":1,"priority":5},
  {"seq":6,"op":"finish","printer":"p1"} ] }
```

`u1` (owner `A`) prints and then finishes, so `A` has now **committed 1 page on
`p1`** (`B` and `C` still have `0`). `hi` prints (priority 9). `u2` (owner `A`)
and `w1` (owner `B`) are submitted while `p1` is busy, so both stay `queued`.
When `hi` finishes, `p1` is dispatched with two eligible jobs of **equal
priority `5`**: `u2` (owner `A`, submit `seq` 4) and `w1` (owner `B`, submit `seq`
5). The priorities tie, so rule 2 decides: `A` has committed `1` page on `p1`
while `B` has committed `0`, so `w1` wins — **even though `u2` was submitted
earlier** (rule 3 is never reached). `spoold printers F` prints:

```json
{
  "printers": [
    {
      "current": "w1",
      "paused": false,
      "printer": "p1"
    }
  ],
  "spool": "F"
}
```

and `spoold queues F` prints (only the still-waiting `u2` remains):

```json
{
  "printers": [
    {
      "printer": "p1",
      "queue": [
        {
          "job": "u2",
          "owner": "A",
          "pages": 1,
          "priority": 5,
          "state": "queued"
        }
      ]
    }
  ],
  "spool": "F"
}
```
