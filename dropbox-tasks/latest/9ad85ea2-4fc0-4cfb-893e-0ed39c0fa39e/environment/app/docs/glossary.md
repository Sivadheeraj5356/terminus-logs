# Glossary

- **counter system** — a fixed set of non-negative integer counters plus
  rewrite rules that consume and produce units atomically.
- **state** — the vector of current counter values.
- **rule** — a `take`/`give` vector pair; enabled when every counter holds at
  least its `take` amount.
- **firing** — applying an enabled rule once: each counter `i` becomes
  `value - take[i] + give[i]`.
- **reachable** — obtainable from the start state by some finite firing
  sequence, of any length.
- **unbounded system** — a system with infinitely many reachable states;
  some counters can be driven arbitrarily high.
- **query** — a target vector; asks whether the system can ever hold at least
  these amounts on all counters at the same time.
- **covered** — the answer is yes: some reachable state dominates the query
  componentwise.
- **malformed verdict** — the whole-job output `{"malformed": true}` produced
  when the job does not conform to the contract.
