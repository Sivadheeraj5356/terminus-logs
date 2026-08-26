# INCIDENT_LOG — Zeckendorf batch encoder

Narrative history. Every algorithmic clause lives in
`/app/src/docs/contracts/`; this file is dated addenda only.

## 2026-06-17  — original brief

Archive team wants a bit-serialized index for integer keys. Two
requirements:

1. The bit representation has to be a **prefix code** — no length field,
   no framing — so index blocks can be concatenated on disk.
2. The mapping from integer to bits has to be a bijection over the
   positives so the archive can reverse it without an out-of-band table.

Fibonacci coding satisfies both. See `contracts/prefix_code.md` for the
current layout and `contracts/zeckendorf.md` for the decomposition.

## 2026-06-19  — batch driver + witness

Rikard added the batch driver. Reads every fixture in
`/app/src/fixtures/`, writes `/app/src/results.json`. The witness
aggregates + chain hash live in `contracts/witnesses.md`.

## 2026-06-27  — todo!() stubs, contract frozen

Library ships to reviewers with `todo!()` bodies. Everything the batch
driver computes derives from the library functions, so a correct
implementation of those is sufficient. Contracts are pinned.

## 2026-07-03  — ZKDF frame + dual coding + verification plane

Three follow-ups landed together — all now pinned in the contracts:

1. **ZKDF frame.** Fixtures are length-prefixed archive records now.
   See `contracts/prefix_code.md §ZKDF frame`.
2. **Elias gamma companion.** Every entry carries both codewords.
   See `contracts/prefix_code.md`.
3. **Primality + golden ratio.** Two extra fields per entry.
   See `contracts/zeckendorf.md`.

The witness object grew `total_elias_bits` + `prime_count`, and a new
`salt_witness` was added at the top level as an independent proof plane
derived only from raw frame headers.

## 2026-07-06  — live runtime policy (INC-2026-ZF1)

Interop harness now rotates a runtime policy between runs. The batch
driver re-reads `/app/config/zeckendorf_policy.json` on every
invocation — schema and semantics in `contracts/policy.md`. Two visible
effects at the results-file level:

- A new `CodewordLengthCap` rejection (see `contracts/rejections.md`)
  terminates the run when any emitted Fibonacci codeword exceeds
  `policy.max_codeword_bits`. Exit code 3.
- A new top-level `policy_witness` scalar joins the existing planes.
  Derivation is in `contracts/witnesses.md` and `contracts/policy.md`.
  `chain_sha256` now binds both witness planes: entries first, then
  `policy_witness`, then `salt_witness` (lex order).

Cohort pinning: the driver refuses to run against a policy whose
`cohort` differs from the compiled constant `INC-2026-ZF1`. That is by
design — stale binaries against rotated policies would otherwise silently
recompute a wrong `policy_witness`.

## 2026-07-07  — module split + variant addendum

The algorithmic surface has been split into five per-concern modules
under `/app/src/src/` — `fibonacci`, `zeckendorf`, `fibonacci_code`,
`elias_gamma`, `primes`. Each ships with `todo!()` bodies; `lib.rs`
carries only the `pub mod` declarations and re-exports so downstream
callers (main.rs, tests) stay untouched.

Two contract additions land alongside:

1. **Variant marker byte** at frame offset 12. `0x00 = canonical`,
   `0x01 = reverse-msb`, anything else = unknown (per-entry zero
   shape with `variant = "unknown"`). Details in
   `contracts/variants.md`. The batch driver's Fibonacci codeword
   emission now consults the marker per fixture — a decoder that
   hardcodes `canonical` fails every `reverse-msb` fixture's canonical
   JSON SHA.
2. **`variant_witness` proof plane** at the top level of
   `results.json`, folded into `chain_sha256` after `salt_witness`
   (lex order — policy, salt, variant). Details in
   `contracts/witnesses.md` and `contracts/variants.md`.

The Elias-gamma zero-value rule was pinned to `"0"` (not the empty
string) in the same push — see `contracts/prefix_code.md §Elias gamma`.
This mostly shows up on unknown-variant and bad-magic entries whose
`n_effective` collapses to zero.

`prime_pi(100) == 25` is folded into the witness aggregate as
`prime_pi_100` so the primes module's second entry point (§primes.rs)
is exercised end-to-end.

## 2026-07-08  — roundtrip witness + contract split

Two changes land together after another interop review.

1. **`roundtrip_witness` proof plane.** A fourth top-level scalar in
   `/app/src/results.json`, derived by decoding each entry's Fibonacci
   codeword back to an integer via `crate::fibonacci_code::fibonacci_decode`
   composed with `crate::zeckendorf::zeckendorf_sum` and comparing to the
   entry's `n`. Per-entry `(roundtrip_ok, bit_len)` pairs are hashed under
   canonical JSON; unknown-variant fixtures force `(false, 0)`. Neither
   field is emitted per-entry — the plane is the aggregate only. Folded
   into `chain_sha256` at its lex position (`policy < roundtrip < salt <
   variant`). Details in `contracts/roundtrip.md`; the top-level key set
   is now seven entries (see `contracts/witnesses.md §1`).

2. **Contract split of `zeckendorf.md`.** The decomposition rule and the
   canonical-form invariants (ascending order + non-consecutive) move
   into their own contract files:

   - `contracts/decomposition.md` — Fibonacci convention, greedy
     algorithm, anti-hardcode rule.
   - `contracts/canonical.md` — ordering, non-consecutive invariant,
     empty-case pinning, round-trip identity.

   `contracts/zeckendorf.md` shrinks to a redirect stub that keeps the
   primality and golden-ratio sections (they never split into a
   sibling). Source docstrings that cite `§zeckendorf.md §Primality` or
   `§Fibonacci convention` still resolve — the redirect names both
   sibling files at the top.

The split ships with two cross-module discipline rules:
`fibonacci_code` must wire the composed decoder through
`crate::zeckendorf`, and `elias_gamma`, `primes`, `zeckendorf` each
must stay independent (no imports across the per-concern boundaries).
Module byte-size floors were bumped roughly 15% to keep the split
honest.

## 2026-07-09 addendum — bracket module + codeword_witness plane

Split the golden-ratio bracketing helper `golden_bracket` out of
`main.rs` into a new `crate::bracket` module. `main.rs` now calls
`crate::bracket::golden_bracket` for the `(phi_p, phi_q)` pair —
`docs/contracts/bracket.md` documents the recipe + cross-module
discipline. The pre-split monolith's inline
`(fibonacci(max_k + 1), fibonacci(max_k))` pattern is a contract
violation. `lib.rs` gains a sixth `pub mod bracket;` declaration and
re-exports `golden_bracket` on the crate root.

Added the fifth proof plane — `codeword_witness` — that binds
`results.json` to the structural shape of every emitted Fibonacci
codeword: the `'1'`-count and the terminating character. The plane's
recipe lives in `docs/contracts/codeword.md`; its position in
`chain_input` is LEX-FIRST among the witness planes (`codeword <
policy < roundtrip < salt < variant`), and the top-level key count
grows from seven to eight (`witnesses.md §1`). Neither `ones_count`
nor `tail_bit` appears per-entry — the plane lives only inside
`codeword_witness`.

## 2026-07-10 addendum — wythoff module + wythoff_witness plane

Added the seventh algorithmic module — `wythoff.rs` — hosting the
Wythoff Beatty-pair helper `wythoff_pair(n) -> (u64, u64)`. The
shipping variant is integer-only: `f32`/`f64`/`.sqrt(` in `wythoff.rs`
are contract violations because `f64` runs out of precision on the
high-`n` shipped fixtures and produces off-by-one `⌊n·φ⌋` values.
`wythoff.rs` imports from `crate::fibonacci` — Newton-style
convergents from Fibonacci ratios are the reference integer route.
See `docs/contracts/wythoff.md`.

Added the sixth proof plane — `wythoff_witness` — a SHA-256 over the
sorted per-entry `{a, b, name}` projection derived from
`wythoff_pair(entry.n)`. The plane lands LEX-LAST in the chain input
(`codeword < policy < roundtrip < salt < variant < wythoff`), and the
top-level `results.json` key count grows from eight to nine
(`witness` still sorts BEFORE `wythoff_witness` because `wi` < `wy`).
Neither `a` nor `b` is emitted per-entry — the pair lives only inside
`wythoff_witness`.
