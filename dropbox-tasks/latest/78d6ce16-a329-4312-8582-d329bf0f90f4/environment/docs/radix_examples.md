# UNITY-47 Radix Notes

UNITY-47 rails use radices 2 through 16. Decimal amounts in the pending feed
are not converted by the CSV loader; the estimator owns radix-specific
interpretation and denomination weighting.

Small rows are useful smoke checks, but production rows include longer decimal
amounts and mixed radices. The report writer should not special-case one
radix, one row length, or the audit-failure sample.

## Carry-heavy regression shapes

These patterns break positive-only expansion and narrow coefficient windows.
Use them to validate a range-complete signed-repunit minimizer (see spec §6.2):

| shape | example amount | radix | why it matters |
|-------|----------------|-------|----------------|
| maximal decimal | `99999999999999999999` (`10^20-1`) | 10 | full 20-digit upper bound |
| repdigit | `2^65-1` | 2 | long run of radix-2 ones |
| alternating high digit | `9934107462565104` | 5 | digit `4` at even positions only |
| mixed-radix repdigit | `16^16-1` | 16 | wide coefficient carry chain |

The alternating base-5 case is a common false-pass for estimators that stop after the
§6.2 small-window probe instead of continuing with the full cost-bounded search.
