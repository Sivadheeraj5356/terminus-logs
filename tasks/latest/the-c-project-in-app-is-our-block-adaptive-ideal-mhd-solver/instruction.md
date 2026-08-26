The C++ project in /app is our block-adaptive ideal-MHD solver, but the numerics are unfinished.
Finish it so that `make` in /app produces /app/bin/amr_mhd and that executable actually advances
two-dimensional ideal magnetohydrodynamics with constrained transport on a two-level, block-adaptive
Cartesian mesh, exactly as /app/docs/mhd-ct-spec.md lays out. The framework around the solver — the
command line, the case and checkpoint formats, the equation-of-state helpers, the initial-condition
presets, the time loop and the diagnostics — is already in place; what is stubbed out is the physics:
the reconstruction and Riemann flux, the constrained-transport electric field, the coarse-fine
synchronisation, the prolongation and restriction between levels, and the refinement criterion. Right
now the stubbed core leaves the field frozen and never refines, so it meets none of the acceptance
properties.

The executable reads one case file (`--case`) and writes the reduced conserved and staggered fields,
together with the conservation, positivity, divergence, refinement and restart diagnostics, to the JSON
path given by `--out`, using exactly the schema, array shapes and cell and face ordering in the spec.
It also writes and resumes from the checkpoint files named by `--checkpoint-out`/`--checkpoint-at` and
`--restart`. The hidden cases it must handle are three-dimensional in the sense that they carry all three
components of velocity and field; they include smooth Alfvén waves, advected field loops, magnetised
blast waves, oblique shock tubes and diverging near-vacuum flows, run both on a single level and with
level-one blocks that are created and destroyed as the flow evolves, including against the domain
boundary.

The constraints are unforgiving and coupled. The magnetic divergence has to stay at machine zero on
both mesh levels at once, and the place it will grow if anything is inconsistent is the cells straddling
a coarse-fine boundary, where the face-normal field must be single-valued and the electric field shared.
Under periodic boundaries the global mass, momentum and energy have to be conserved to round-off even
while fine blocks overlie the coarse grid, which only holds if the fluxes are reconciled across the
interface. Density and pressure must stay strictly positive through strong fast shocks and into near
vacuum. A smooth wave has to converge at second order. A run broken at a checkpoint — including one taken
after the mesh has been regridded — must reproduce the unbroken run's fields, and repeating any run,
with its blocks reported in a fixed canonical order, must reproduce the output bit for bit. Keep it C++
built by the toolchain already in /app, add no dependencies, and expect no network.
