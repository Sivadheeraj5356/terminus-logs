# plangen

`plangen` is a model-evaluation tool for post-hoc confidence calibration. Given
a trained multi-class classifier's held-out predictions, it fits calibration
maps on a fit fold, measures expected calibration error under distribution
shift, and reports which calibration family stays within each stage's ECE
budget.

## What a bundle holds

A bundle is a record of one trained model's held-out inference. For every sample
it carries the model's raw confidence score, whether that prediction was correct
(`hit`), and the subgroup (`lane`) the sample was drawn from. Raw scores are not
probabilities. The model is overconfident, so a raw score of 700 out of a `unit`
of 1000 does not mean the model is right 70 percent of the time. Post-hoc
calibration fits a map from raw score to calibrated confidence so that it does.

## The families

Three calibration families may be fitted, ordered by increasing strength.

| family | strength | what it fits |
|--------|----------|--------------|
| `hist` | 0 | uniform histogram binning over the raw score range |
| `iso` | 1 | isotonic regression, pooled over all samples |
| `giso` | 2 | isotonic regression fitted separately per subgroup |

A stronger family can represent everything a weaker one can. Which family a
stage needs depends on how far its data has drifted, and on whether the drift is
shared across subgroups or differs between them.

## Why a ladder

A model is fitted once, then deployed into conditions that drift away from the
data it was fitted on. A bundle records that drift as a ladder with a shared fit
fold, plus a list of rungs ordered by `severity`. Rung 0 sits closest to the
fit fold; later rungs sit further away. Each rung carries its own `budget`, how
much calibration error is tolerable at that stage.

Every family is fitted on the fit fold and only on the fit fold. A rung's own
samples are what the calibrated model is being judged against, so fitting on
them would be marking your own homework; the numbers would look excellent and
mean nothing. Equal-mass edges are a separate concern. The optional rim rows
take part only in placing those edges, together with the fit fold, and never in
fitting a map. Measuring a rung with edges drawn from the rung itself, or from
the fit fold alone when a rim is present, is not the documented procedure.

## Layout

| path | role |
|------|------|
| `/app/environment/cmd/plangen` | the command line entry point |
| `/app/environment/internal/model` | shared row, rung, bundle, and document types |
| `/app/environment/internal/io` | reads and validates bundles; never writes to them |
| `/app/environment/internal/frac` | exact integer rounding and cross-multiplication |
| `/app/environment/internal/order` | deterministic ordering helpers |
| `/app/environment/tabulate` | fits histogram and isotonic calibrators on the fit fold |
| `/app/environment/spread` | measures ECE of a fitted calibrator over a shift rung |
| `/app/environment/arrange` | selects one calibration family per shift severity |
| `/app/environment/render` | writes the calibration evaluation report |
| `/app/environment/stow` | digest-keyed sealed reliability edges under `/app/environment/var/fitstore` |
| `/app/environment/trail` | interrupted-evaluation resume state under `/app/environment/var/run` |
| `/app/environment/data/bundles` | small format examples |
| `/app/environment/docs` | the contract, protocol, and schemas |
| `/app/environment/var/` | durable fit store and plan journals |

## Building

```
make -C /app/environment rebuild
```

builds `/app/bin/plangen`. The build is offline. The module has no third-party
dependencies and `GOPROXY` is off.

## Commands

```
/app/bin/plangen plan  --input <bundle.json> --out <plan.json>
/app/bin/plangen stats --input <bundle.json>
```

`plan` writes the report described in `/app/environment/docs/plan-format.rst`.
`stats` writes a short descriptive trace to standard error (populated cell
count, the raw score window, and per-rung sample counts) and writes no report.
`stats` is an aid for looking at a bundle; nothing it reports takes part in
fitting, evaluating, or selecting.

## Reading order

Start with `/app/environment/docs/model-evaluation.md` for the model-evaluation
role. `/app/environment/docs/contract.rst` is the authority on every number.
`/app/environment/docs/protocol.rst` is the authority on sealed reliability edges
and interrupted-evaluation resume. `/app/environment/docs/input-format.rst` and
`/app/environment/docs/plan-format.rst` define the two schemas. This page is
orientation only; where it and those pages disagree, those pages win.
