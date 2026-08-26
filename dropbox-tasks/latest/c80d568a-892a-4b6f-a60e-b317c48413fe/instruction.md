The Rust library at /app/src/src/ is split across nine per-concern
modules — `fibonacci`, `zeckendorf`, `fibonacci_code`, `elias_gamma`,
`primes`, `bracket`, `wythoff`, `negafibonacci`, `pisano`. Each ships
with unimplemented bodies; lib.rs only re-exports. Replace every stub
so the batch driver produces the expected /app/src/results.json.

The algorithmic contract lives under /app/src/docs/contracts/:
`decomposition.md`, `canonical.md`, `zeckendorf.md`, `prefix_code.md`,
`variants.md`, `roundtrip.md`, `bracket.md`, `codeword.md`,
`wythoff.md`, `witnesses.md`, `policy.md`, `rejections.md`,
`negafibonacci.md`. Contracts win over SPEC.md, INCIDENT_LOG.md, and
every source-file docstring. Source comments in /app/src/src/ may be
out of date or affirmatively wrong.

Fixtures under /app/src/fixtures/ are ZKDF-framed records — 4-byte
magic, LE u64 salt, one variant marker byte, JSON tail — decoded via
salt XOR before Zeckendorf decomposition (prefix_code.md §ZKDF frame).
The variant marker byte selects `canonical` (0x00), `reverse-msb`
(0x01), or `unknown` (anything else) per fixture; see variants.md.

The runtime policy at /app/config/zeckendorf_policy.json carries a
cohort pin, a Fibonacci-codeword bit cap, and a witness salt. The
batch driver re-reads it on every invocation. Cap violations trigger
`CodewordLengthCap`. Six witness planes (codeword_witness,
policy_witness, roundtrip_witness, salt_witness, variant_witness,
wythoff_witness) join the entry SHAs in the chain_sha256 composition —
see witnesses.md, roundtrip.md, codeword.md, and wythoff.md.

`wythoff.rs` is integer-only — no `f32`/`f64`/`.sqrt(` per
docs/contracts/wythoff.md.

The `decoy` module at /app/src/src/decoy/ is not on the decode path.

`crate::negafibonacci` (`docs/contracts/negafibonacci.md`) is the
signed-integer Zeckendorf variant. Batch mode does not touch it;
instead the same binary handles the one-off subcommand
`./target/release/zeckendorf-encode negafib --n <signed_int>`, which
prints one canonical-JSON line
`{"indices":[...],"is_minimal":true,"n":<n>,"reconstructed":<n>}` on
stdout. Uses the shared `crate::fibonacci` table (do not re-implement
the recurrence locally). Two rejection paths — `SumOverflow` on
`|n| > 10^18` (exit 4) and `NonMinimalNegafibonacci` on a
non-canonical or non-reconstructing decomposition (exit 5).

`crate::pisano` computes the Pisano period π(m) — the smallest
positive `p` such that the Fibonacci sequence modulo `m` repeats with
period `p` (Wall 1960; OEIS A001175). Batch mode does not touch it;
the same binary handles the one-off subcommand
`./target/release/zeckendorf-encode pisano-period --m <u64>`, which
prints one canonical-JSON line `{"m":<m>,"pisano_period":<p>}` on
stdout (keys lex-sorted). Recipe under the crate's F_2 = 1 convention:
seed `(a, b) = (1 mod m, 2 mod m)`, advance `(a, b) ← (b, (a+b) mod m)`,
count steps until `(a, b)` returns to the seed. Boundary: `π(1) = 1`.
Two rejection paths — `NonPositiveModulus` on `--m 0` (exit 6) and
`ModulusOverflow` on `--m > 10^9` (exit 7).

Build with `cargo build --release --offline --locked` from /app/src
and run `./target/release/zeckendorf-encode --fixtures
/app/src/fixtures --out /app/src/results.json`.

No external crate. No internet. No shelling out.
