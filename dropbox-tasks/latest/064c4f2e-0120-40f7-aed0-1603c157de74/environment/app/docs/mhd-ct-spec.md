# amr_mhd — solver contract (v1)

This document is the authority for the `amr_mhd` executable. It fixes the equations, the
numerical scheme, the mesh, the file formats and the acceptance invariants. It does not
prescribe an implementation.

## 1. Physical model

Ideal magnetohydrodynamics in two Cartesian dimensions, evolving the full three-component
velocity `(u,v,w)` and magnetic field `(Bx,By,Bz)` (a planar mesh, `d/dz = 0`). A gamma-law
equation of state with ratio of specific heats `gamma` (default `5/3`).

Conserved cell quantities are density `rho`, momentum `(rho u, rho v, rho w)` and total
energy `E`. The magnetic field is staggered: `Bx` lives on x-faces, `By` on y-faces, and
`Bz` is cell-centered. The cell-centered in-plane field used for reconstruction and for the
equation of state is the arithmetic average of the two opposing face values.

```
E   = p/(gamma-1) + 1/2 rho (u^2+v^2+w^2) + 1/2 (Bx^2+By^2+Bz^2)
ptot= p + 1/2 (Bx^2+By^2+Bz^2)
```

The divergence constraint is `dBx/dx + dBy/dy = 0`, discretised on each cell from its face
fields. It must hold to machine precision at all times and on every mesh level (§6).

## 2. Discretisation

- Finite-volume Godunov update in conservative form for the hydro quantities and `Bz`.
- Spatial reconstruction: piecewise-linear MUSCL on the primitive variables
  `(rho,u,v,w,p,Bx,By,Bz)` with the monotonized-central (MC) limiter. First-order (unlimited
  piecewise-constant) reconstruction does not meet the convergence requirement of §6.
- Interface flux: the HLL approximate Riemann solver, with signal speeds bounded by the fast
  magnetosonic speed. The face-normal field entering the Riemann state is the staggered face
  value, not a reconstructed cell average.
- Magnetic update: constrained transport with the Balsara–Spicer arithmetic-averaging electric
  field. The corner electric field `Ez` is the average of the four adjacent face-centred line
  integrals derived from the Riemann fluxes; the face fields are advanced by the discrete curl
  of `Ez`. A scheme built this way keeps the discrete divergence unchanged by construction.
- Time integration: the two-stage strong-stability-preserving Runge–Kutta method (SSP-RK2),
  the magnetic field advanced by constrained transport at each stage.
- Time step: `dt = cfl * min over active cells of ( dx/(|u|+cf_x), dy/(|v|+cf_y) )`, with the
  minimum taken over both mesh levels at their own cell size (`cfl` default `0.4`). A single
  global time step advances both levels; there is no temporal subcycling of the fine level.
- Positivity: whenever a reconstructed or updated state has `rho < 1e-9` or `p < 1e-9`, the
  offending quantity is restored to that floor and the event is counted. The floor must keep
  every reported density and pressure strictly positive in strong shocks and near vacuum.

## 3. Boundary conditions

`bc = periodic` (default for every preset except `rotated_shock`) wraps both directions.
`bc = outflow` applies zero-gradient (nearest-interior copy) on all four domain edges. The
divergence constraint and the coarse–fine treatment apply identically under either.

## 4. Mesh and adaptivity

- Level 0 is a uniform `nx x ny` grid over `[0,Lx] x [0,Ly]`.
- Level 1 refines level 0 by a factor of two. The refined region is a union of square
  **blocks** of `block x block` fine cells (`block` even; a block covers `block/2` square coarse
  cells). The set of active blocks is the adaptive structure.
- Refinement is driven by a deterministic indicator. Let `S_rho`, `S_p` and `S_B` be the maxima
  of `rho`, `p` and `|B| = sqrt(Bx^2+By^2+Bz^2)` over the level-0 interior, evaluated on the
  cell-centred state at the moment of the regrid. For each level-0 cell `(I,J)`, using the
  boundary-filled neighbours,

  ```
  chi(q,S) = ( |q(I+1,J) - q(I-1,J)| + |q(I,J+1) - q(I,J-1)| ) / (2 S)
  chi      = max( chi(rho,S_rho), chi(p,S_p), chi(|B|,S_B) )
  ```

  and the cell is tagged when `chi >= refine_threshold`. A block is tagged when any level-0 cell
  inside it is tagged. The tagged block set is then grown by one block in each of the eight
  neighbouring directions (wrapping under periodic boundaries, clipped under outflow) so the
  refined region is properly nested and contiguous; that grown set is the active set. It is
  recomputed every `regrid_interval` steps, so blocks are created and destroyed as the flow
  evolves, including at the domain boundary.
- The active set may instead be pinned explicitly with the `blocks` key (§5), which bypasses the
  indicator. A pinned layout is not required to be rectangular, contiguous or interior: it may be
  a single block, an L, a ring enclosing unrefined cells, or a set that touches or straddles a
  periodic seam, and every acceptance invariant of §6 still applies to it unchanged.
- Coarse–fine coupling must keep the whole solution consistent: global conserved quantities are
  preserved to round-off across the interface (flux refluxing), the face-normal field is
  single-valued there (a coarse face equals the average of the two fine faces it covers), and
  the divergence stays at machine zero on both levels including the coarse cells that touch the
  interface (electric-field synchronisation). Data introduced on newly refined blocks is
  interpolated from level 0 so that it is divergence-free and conserves the coarse averages.
- Block iteration order is canonical: ascending `bj`, then ascending `bi`. Ties in the
  refinement decision are broken by this fixed order. Odd numbers of active blocks are allowed.

## 5. Command line

```
amr_mhd --case <case> --out <result.json>
        [--checkpoint-out <path> --checkpoint-at <step>]
        [--restart <path>]
```

`--case` selects the run; `--out` is the JSON result (§7). If `--checkpoint-out`/`--checkpoint-at`
are given, a restart file is written after the named step. `--restart` resumes from such a file
and then applies the remaining run controls (`nsteps`/`tmax`/`regrid_interval`) from `--case`.

### Case file

Lines of `key = value`; `#` starts a comment. Recognised keys and defaults:

```
preset            cpaw | field_loop | blast | vacuum | rotated_shock   (cpaw)
nx, ny            coarse cell counts                                    (32)
Lx, Ly            domain size                                           (1.0)
block             fine cells per block edge, even                       (8)
amr               1 to enable level 1, 0 for single level               (1)
bc                periodic | outflow                                    (preset default)
cfl               Courant number                                        (0.4)
gamma             ratio of specific heats                               (5/3)
refine_threshold  refinement indicator threshold                        (0.2)
regrid_interval   steps between regrids, 0 to never regrid              (0)
blocks            pin the active set, e.g. "0,0 1,0 1,1" (bi,bj pairs); (unset)
                  overrides the indicator for the initial mesh          
nsteps            stop after this many steps (takes priority)           (0)
tmax              stop time                                             (0)
alpha             wave/interface angle for cpaw and rotated_shock       (pi/4)
amp, B0           preset amplitude / background field                   (preset)
cx, cy            feature centre as a fraction of the domain            (0.5)
```

Presets:

- `cpaw` — circularly polarised Alfvén wave travelling along `alpha`, an exact nonlinear
  solution used for the convergence check; periodic.
- `field_loop` — a weak magnetic field loop in a uniform advecting flow; periodic.
- `blast` — a pressure-driven blast in a magnetised medium; strong fast shocks; periodic.
- `vacuum` — diverging streams that rarefy toward vacuum; periodic.
- `rotated_shock` — an oblique MHD shock tube along `alpha`; outflow.

## 6. Acceptance invariants

A correct solver satisfies all of the following on the hidden cases:

1. **Convergence** — for the smooth `cpaw` wave the L1 error of the reduced field against the
   exact solution falls at second order under grid refinement.
2. **Divergence** — `max |div B|` is at the level of round-off on level 0 and, with `amr=1`,
   on the active level-1 blocks, including cells adjacent to a coarse–fine boundary.
3. **Face continuity** — on a coarse–fine interface the coarse face-normal field equals the
   average of the two fine faces covering it.
4. **Conservation** — under periodic boundaries the global mass, each momentum component and
   the total energy are constant in time to round-off, with level 1 active.
5. **Positivity** — density and pressure stay strictly positive in strong shocks and near
   vacuum.
6. **Restart** — a run split by a checkpoint (including one taken after a regrid) reproduces
   the un-split run's fields exactly.
7. **Determinism** — repeating a run reproduces the output bit-for-bit, and the active block
   list is in canonical order.

## 7. Result schema

`--out` is a single JSON object. Scalars are written at full double precision.

```
preset, bc, nx, ny, Lx, Ly, block, gamma, t, steps            run metadata
nblocks                                                       number of active level-1 blocks
block_order   [[bi,bj], ...]                                  active blocks, canonical order
mass0, momx0, momy0, momz0, energy0, magE0                    conserved totals at t=0
mass,  momx,  momy,  momz,  energy,  magE                     conserved totals at t
min_rho, min_p                                                minima over active cells
maxdivB_coarse, maxdivB_fine                                  reported divergence norms
l1                                                            cpaw L1 error (0 otherwise)
protect                                                       positivity-floor event count
coarse : { rho,u,v,w,p,bz : nx*ny (row-major, j*nx+i),
           bx : (nx+1)*ny, by : nx*(ny+1) }                   level-0 cell and face fields
blocks : [ { bi,bj,bf, rho,u,v,w,p,bz : bf*bf,
             bx : (bf+1)*bf, by : bf*(bf+1) }, ... ]           active level-1 blocks, canonical order
```

Totals and minima are taken over level-0 cells not covered by a level-1 block plus all active
level-1 cells. Face arrays are stored so that `bx[j*(n+1)+i]` is the field on the x-face left of
cell `i` in row `j`, and `by[j*n+i]` is the field on the y-face below cell `j` in column `i`.

## 8. Checkpoint

The restart file is written by the executable and read back by it; its layout is the
executable's own concern. It must capture enough of the state — both levels, the staggered
fields, the active block set, the time and the step counter — that a resumed run is
indistinguishable from an unbroken one.
