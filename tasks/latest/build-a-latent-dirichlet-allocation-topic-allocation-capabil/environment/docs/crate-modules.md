# Crate module layout

The working workspace under `/app` ships `ldacore` as a multi-module crate. Agents may change module bodies to meet the CLI contracts, but must preserve the on-disk module paths and the public function signatures that `ldactl` and `ldacore::engine` already call. Renaming or collapsing these modules so those call sites no longer compile is out of contract.

Required module files (each is `crates/ldacore/src/<name>/mod.rs`):

| Module | Required public surface used by the workspace |
|--------|-----------------------------------------------|
| `corpus` | `pub fn build(docs: Vec<RawDoc>) -> Result<CorpusStaging>` |
| `vocab` | `pub fn build(docs: &[RawDoc]) -> Vec<String>` |
| `rng` | `seed_state`, `next_u64`, `uniform`, `init_topic` with the same argument types as the shipped stubs |
| `sampler` | `conditional(n_dk, n_kw, n_k, alpha, beta, v) -> f64` and `choose(masses, draw) -> usize` |
| `ledger` | `add` and `remove` over the count matrices with the shipped argument order |
| `retention` | `should_accumulate`, `accumulate`, `retained_count` |
| `ranking` | `top_terms(...)` returning the ranked term list used by publication |
| `publication` | `pub fn build(corpus_bytes: &[u8], count_bytes: &[u8], cfg: &Config) -> Result<Rollup>` |

`crates/ldacore/src/lib.rs` must continue to declare these modules. The decoy under `crates/ldacore/src/decoy/` remains non-authoritative and must not be required on the ingest/sample/export hot path.
