# Counter-system analysis contract

This document defines counter systems, the cover question the analyzer must
answer, and the exact I/O obligations. It defines what a correct verdict is,
not how to compute it.

## 1. Counter systems

A system has `counters` non-negative integer counters. Its state is the vector
of their values; the initial state is `start`. A rewrite rule has two vectors
of length `counters`: `take` and `give`. A rule is **enabled** in a state when
every counter `i` holds at least `take[i]`. Firing an enabled rule replaces
counter `i` by `value - take[i] + give[i]`, for every `i` simultaneously.

A state is **reachable** when some finite sequence of enabled firings leads to
it from the start state (the start state itself is reachable). Nothing bounds
how many times a rule may fire: systems in this class can have infinitely many
reachable states, with counters that grow without limit.

## 2. The cover question

A query is a vector of length `counters`. The query is **covered** when there
exists a reachable state that is at least the query on every counter
simultaneously. The analyzer must answer every query in the job with exactly
this truth value.

Two obligations follow:

- **Exactness.** The verdict must reflect reachability at any depth: a query
  covered only by states that take very many firings to reach is still
  covered, and a query is uncovered only if no reachable state whatsoever
  covers it — approximations in either direction are not conforming.
- **Termination.** The analyzer must decide every conforming job in bounded
  time, including systems whose reachable state space is infinite. Failing to
  answer is not conforming.

## 3. Validation

A job that does not conform produces the malformed verdict (see
`/app/docs/output_schema.md`) instead of verdicts. Non-conforming jobs
include: `counters` outside `1..12`; more than 16 rules or more than 32
queries; any `take`, `give`, `start`, or query vector missing, of the wrong
length, or holding anything other than integers in `0..1000`; or any
wrongly-typed field.

## 4. Worked example

`counters = 2`, `start = [1, 0]`, one rule: `take = [1, 0]`,
`give = [1, 1]`.

The rule keeps counter 0 at 1 and adds one unit of counter 1 per firing, so
the reachable states are `[1, k]` for every `k >= 0`.

Queries `[1, 5]` and `[0, 400]` are covered; `[2, 0]` is not (counter 0 never
exceeds 1):

```json
{"covered": [true, true, false]}
```
