# Input and output format

## Input (JSON)

The run description is a flat JSON object. `input/transport.json` is the default
example. Fields:

| key         | meaning                                                    |
|-------------|------------------------------------------------------------|
| `c`         | wave speed (positive)                                      |
| `g`         | damping rate (positive)                                    |
| `N`         | number of grid cells                                       |
| `nu`        | Courant number used to size the time step                  |
| `T`         | final time                                                 |
| `snapshots` | increasing list of times at which to record the field      |

The initial displacement profile is selected by `kind`, either `"gaussian"` or
`"sinsum"`. The field starts from rest, so the initial velocity is zero.

For a Gaussian profile:

| key      | meaning            |
|----------|--------------------|
| `center` | center of the bump |
| `width`  | width of the bump  |

For a sinusoid-sum profile:

| key      | meaning                                    |
|----------|--------------------------------------------|
| `const`  | constant term                              |
| `amps`   | list of amplitudes                         |
| `waves`  | list of integer wavenumbers (same length)  |
| `phases` | list of phases (same length)               |

## Grid

The grid is pinned to

    x_i = i / N,   i = 0 .. N-1,   dx = 1 / N.

## Output (CSV)

The program writes `output/field.csv` with the header line

    t,x,u,v

followed by one row per snapshot time and grid point. Within each snapshot the
`N` points appear in increasing `x`; snapshots appear in the order listed in the
input. Each row lists the time, the coordinate, the displacement `u`, and its
time derivative `v = u_t` at that point. Every value is written in full double
precision.
