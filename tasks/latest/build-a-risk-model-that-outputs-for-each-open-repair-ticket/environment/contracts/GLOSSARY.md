# Glossary

- **Open ticket** - a ticket in the newest `service_month` whose `repeat_visit` outcome is
  blank and must be scored; the open batch sits a few months past the last labeled month.
- **Repeat truck-roll** - a second field visit needed within thirty days of the first.
- **Calibrated probability** - a score matching the observed repeat rate, overall and within
  each `equipment_class` across the `job_complexity` range.
- **Saturating drift** - the repeat rate rises across `service_month` and decelerates; the
  flattening is estimable only from the full labeled history, so a recent-window or linear
  extrapolation misprices the open batch.
- **Cost-optimal threshold** - the cut-off minimizing expected cost under the asymmetric
  weights (a missed repeat costs five times a needless senior dispatch).
- **Cold-start class** - an `equipment_class` present only in the newest month, scored from a
  sensible fallback so it is still ranked.
- **Provisional field** - a column carrying a settled value on resolved tickets but only a
  provisional placeholder on open ones; not a legitimate model input.
