# Estimand contract

## Quantity to estimate

The target is the average treatment effect (ATE) of enrolling in the wellbeing
program on the end-of-year wellbeing index, averaged over the entire population
of employees represented in the records. Concretely, it is the average change in
the `wellbeing_index` that enrolling causes for an employee drawn at random from
this population, expressed in the units of `wellbeing_index`.

## Population

The full set of employees in the data, not any subgroup, and not only the
enrolled. Because the program's effect varies from employee to employee, the
number reported is the average of that varying effect over the whole population,
not the effect for a single representative employee and not the effect only among
those who enrolled.

## What "causal" means here

The number must reflect the effect of enrollment itself, with the influence of
the pre-existing differences that shaped who enrolled accounted for, so that it is
not contaminated by differences that were already present between enrolled and
non-enrolled employees before the program began.

## Deliverable

A single point estimate written to `/app/estimate.json` (see `output_schema.md`).
