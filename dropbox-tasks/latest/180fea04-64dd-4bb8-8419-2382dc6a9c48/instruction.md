Single-molecule force spectroscopy watches one protein hop between its folded and
unfolded states while an optical trap holds it at a fixed load. Each hop is a
diffusive crossing of the free-energy barrier, so the unfolding and folding rates
measured at every load carry the shape of the landscape. Two things sit in the
way: each molecule's bead and linker geometry shifts its attempt frequency, and
each trap calibration misreads the load it actually applied, so the force that
enters the rate is not the force on the dial. Neither is observed and both differ
from molecule to molecule.

/app/data/study.sqlite holds one study: landscape constants for this construct,
twenty molecules, and unfolding and folding log-rates at five clamp forces each.
The landscape, the passage-time definition of the two rates, the measurement
model and the estimator the group settled on are written up in /app/MODEL.md.
Standard ML is the working language here, /app/src carries a skeleton, and the
native executable belongs at /app/bin/folding; the analysis stays in Standard ML
rather than shelling out to another runtime.

Report the barrier scale, the desolvation amplitude and the diffusion coefficient
together with the three noise scales, and alongside them:

- marginal standard errors for those first three;
- the deviance against a landscape carrying no desolvation feature;
- the coexistence force, and the folding rate extrapolated to zero load.

Write the report to /app/output/report.json. /app/run.sh takes the database and
the report path as its first two arguments; it has to work on any study with this
schema, from any working directory, inside ten minutes.
