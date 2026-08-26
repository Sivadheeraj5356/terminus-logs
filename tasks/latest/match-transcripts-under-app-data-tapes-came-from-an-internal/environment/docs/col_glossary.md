# column glossary

GRTIROW labels use pipe fields: arm, band, seq counter, epoch mark, replay prefix.

Status tokens in interim tallies:

- `ROW_OK` local row shape matches
- `ROW_GAP` missing tail segment
- `LANE_IDLE` ko lane not advanced

These tokens describe presentation only. Graded binding uses collector replay bytes documented in pact_k7.md.
