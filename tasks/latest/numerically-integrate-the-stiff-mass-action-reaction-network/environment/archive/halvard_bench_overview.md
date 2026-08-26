# Halvard Kinetics Bench

The Halvard bench certifies concentration trajectories for the mass-action reaction
networks used across the facility's assay pipeline. Every certified run reports the
concentrations reached at the network's horizon, how many integration steps the
protocol accepted and rejected, how many derivative evaluations it spent, and a
verdict recording whether the horizon was reached at all.

Certification was the facility's unit of record: two runs of the same network under
the same tolerances are expected to agree exactly, down to the step counts, and a
result that does not reproduce is not certified.

## Scope of the surviving instrument

The bench executable integrates only the twelve calibration systems compiled into
it. It reads no network files. Assay networks were fed to the assay service, which
was decommissioned along with the rest of the integrator sources when the group
moved off the platform; the bench survived because it is the calibration reference
and was kept on the instrument host.

## Stage weights

At start-up the bench loads its stage weight table from `bench/stage_weights.tsv`.
The table carries the node offsets, the lower-triangular stage matrix, and the two
companion weight rows of the embedded pair the bench was commissioned with. The
table is part of the instrument's calibration record and is not expected to change.

## Calibration systems

`calibration/` holds one network file per compiled-in calibration system, written in
the same form the assay service consumed. The bench's own run of a calibration
system and the matching network file describe the same chemistry, so the two can be
compared directly.

`archive/calibration_index.tsv` summarises the suite: species count, reaction count,
horizon, and the tolerances each system is certified at.

## Assay networks

`assay/` holds a few networks left behind in the retired service's working
directory. They are ordinary assay networks and carry no certified result.
