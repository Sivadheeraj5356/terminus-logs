# decomposition.md — Fibonacci convention + greedy decomposition

Authoritative for `fibonacci`, `fib_index_of`, `zeckendorf_indices`,
`zeckendorf_sum`. Canonical-form invariants (non-consecutive indices,
ascending output order) live in `canonical.md`; the primality companion
lives in `zeckendorf.md`'s primality section (now redirect stub).

## Fibonacci convention

Zeckendorf-numbered Fibonaccis, indexed from k = 2:

    F_2 = 1
    F_3 = 2
    F_4 = 3
    F_5 = 5
    F_6 = 8
    F_7 = 13
    F_8 = 21
    ...
    F_k = F_{k-1} + F_{k-2}      for k >= 4

`F_0` and `F_1` do NOT exist in this crate's convention. `fibonacci(k)`
for `k < 2` MUST panic. The textbook `F_0 = 0, F_1 = 1, F_2 = 1,
F_3 = 2, ...` variant is **wrong** for this crate — a decoder that
seeds `(a, b) = (0, 1)` and returns `b` at step `k` produces every
fixture's `zeckendorf_indices` off by one against the shipping SHAs.

`fib_index_of(n)` returns the greatest `k >= 2` such that
`fibonacci(k) <= n`, or `None` when `n < 1`. The greedy uses it to
locate the top index without a fresh linear scan through `fibonacci`.

## Zeckendorf decomposition (top-down greedy)

For every non-negative integer `n_effective` there is a **unique** set
of Fibonacci indices `S ⊆ {2, 3, 4, ...}` satisfying

    sum(F_k for k in S) == n_effective   AND   no two elements of S are consecutive.

`zeckendorf_indices(n_effective)` returns that set as a `Vec<u32>`. The
ordering convention and non-consecutive invariant are pinned by
`canonical.md`; both are load-bearing against the shipping SHAs.

For `n_effective = 0` the set is empty. For `n_effective = 1` it is
`[2]`. For `n_effective = 4` it is `[2, 5]` (1 + 3 — indices 2 and 5).

The correct greedy is **top-down**: locate the largest `F_k` with
`F_k <= n_effective` (use `fib_index_of`), subtract it, then repeat
with the remainder against indices `k - 2` and below. A bottom-up
sweep (accumulating F_2, F_3, … into a running sum) does **not**
produce the canonical decomposition and routinely violates the
non-consecutive invariant. The non-consecutive invariant is a
property the correct algorithm has to preserve, not one you can drop
from the check on the assumption the algorithm handles it.

`zeckendorf_sum(indices)` is the inverse — sum `fibonacci(k)` across
the index list. `zeckendorf_sum(zeckendorf_indices(n)) == n` for
every `n`.

## Do not hardcode Fibonacci values in the zeckendorf module

Every Fibonacci lookup inside `zeckendorf.rs` MUST go through
`crate::fibonacci::fibonacci`. Copy-pasting an `[1, 2, 3, 5, 8, 13,
21, 34, 55, 89, 144, 233, 377, 610, 987, ...]` lookup table into
`zeckendorf.rs` is the "cheat by table-recall" shortcut and is a
contract violation. `zeckendorf.rs` MUST use `crate::fibonacci` for
every Fibonacci lookup and MUST NOT depend on `crate::fibonacci_code`
(the greedy layer cannot depend on the codeword serialiser).
