# Status lexicon

Rare status tokens written into graded and partial probe rows.

| Token | Meaning |
|-------|---------|
| `WIT_FRESH` | Graded row regenerated from live sources with coherent surfaces |
| `PARTIAL_OK` | Property-only / smoke sample; not a graded suite success |
| `SEL_DRIFT` | Selection id diverges from activated arm fragment expectations |
| `ORD_GAP` | Fetch sequence ignores conf activation order |
| `SCHEME_LEGACY` | Loader scheme remains legacy-only for a provider-capable URI |

Interpret suite output using these tokens. `PARTIAL_OK` on a prop-only run does not imply full-suite agreement.
