# Wave Integrator Contract

Authoritative specification for the memory-capped 2D wave integrator under `/app/`.

## Command Line

Entrypoint script `/app/run_entry.js` is deployed from the environment package at `/app/environment/`. Equivalent invocation:

`node /app/environment/../run_entry.js config.json output.json`

```
node /app/run_entry.js <config.json> <output.json> [--checkpoint PATH] [--resume]
```

- `--checkpoint PATH`: after each completed step, persist leapfrog state to `PATH`.
- `--resume`: load state from `PATH` and continue from the saved step index (requires matching `gridSize` and `order` in config).

## Physics

2D wave equation with fixed wave speed `c = 1.0`:

```
∂²u/∂t² = c² (∂²u/∂x² + ∂²u/∂y²)
```

Leapfrog time update:

```
u^{n+1} = 2·u^n − u^{n−1} + c²·dt²·Δu^n
```

### Spatial discretization (dy = dx)

**Order 2** Laplacian at interior index `(i,j)`:

```
Δu ≈ (u[i+1,j] + u[i−1,j] + u[i,j+1] + u[i,j−1] − 4·u[i,j]) / dx²
```

**Order 4** Laplacian:

```
Δu ≈ (−u[i+2,j] − u[i−2,j] − u[i,j+2] − u[i,j−2]
      + 16·(u[i+1,j] + u[i−1,j] + u[i,j+1] + u[i,j−1]) − 60·u[i,j]) / (12·dx²)
```

## CFL limits

Reject the run (non-zero exit, stderr contains `CFL`) when `dt` exceeds:

| Order | dtMax |
|-------|-------|
| 2 | `dx / (c · √2)` |
| 4 | `√(3/7) · dx / (c · √2)` |

## Per-step pipeline

Each time step **must** execute in this order:

1. **reconcile-pre**: apply edge constraints to `curr`
2. **phase_b**: write interior stencil update into `next`
3. **reconcile-post**: apply edge constraints to `next`
4. **swap**: rotate `prev ← curr`, `curr ← next`, `next ← prev`
5. **sample_d**: if `step % stride == 0`, append a deep-copied interior snapshot to traces

Step 0 trace is taken after initial pulse placement and initial reconcile-pre.

## Index layout

Ghost width `H = 2`. Padded width `W = gridSize + 2·H`. Flat index:

```
idx(i, j) = (i + H) · W + (j + H)     // i,j are interior cell coords 0..gridSize−1
```

Allocation helper `op_a(gridSize, dims)` returns `{ prev, curr, next, width, height, gridSize, ghost }` where each of `prev`, `curr`, `next` is an independent zero-initialized `Float64Array` of length `W·W`. Sequential calls must not share mutable storage; pool reuse must zero slabs before handoff.

## Edge reconciliation

Load boundary types from the halo fixture selected by config key `haloProfile`:

| haloProfile | fixture path |
|-------------|--------------|
| `default` (or absent) | `/app/fixtures/halo_configuration.json` |
| `mixed` | `/app/fixtures/halo_mixed.json` |

Each fixture provides `boundaries.left|right|top|bottom` as `dirichlet` or `neumann`.

- **Dirichlet**: set ghost cells to `0`.
- **Neumann**: mirror interior values across the edge (`u_{ghost} = u_{interior+d}`).

**Corner precedence**: apply horizontal edges (left, right) for all rows first, then vertical edges (top, bottom) for all columns.

## Trace sampler `sample_d`

`sample_d(buffers, step, t)` extracts the `gridSize × gridSize` interior from `buffers.curr` in row-major order. Each returned vector must be a **deep copy** — later mutations to `curr` must not alter previously emitted trace entries.

## Checkpoint binary layout

Checkpoint path is supplied via `--checkpoint` (for example `/app/work/sim.ckpt`). Binary layout:

| Offset | Size | Field |
|--------|------|-------|
| 0 | 4 | magic `WJCK` (bytes 0x57 0x4A 0x43 0x4B) |
| 4 | 4 | version `uint32 LE` = 1 |
| 8 | 4 | step `uint32 LE` |
| 12 | 4 | epoch `uint32 LE` |
| 16 | 4 | gridSize `uint32 LE` |
| 20 | 4 | order `uint32 LE` |
| 24 | 8 | checksum `uint64 LE` FNV-1a over bytes `[32 .. 32+2·W·W·8)` |
| 32 | 8·W·W | prev raw Float64 LE |
| 32+8·W·W | 8·W·W | curr raw Float64 LE |

`W = gridSize + 4`. On resume, reject corrupted or stale bundles: checksum or epoch mismatch must exit non-zero with stderr containing `epoch` or `checksum`.

Checkpoint must be written **after** the per-step buffer swap. The saved `prev` and `curr` are the leapfrog pair at the end of the completed step (`prev = u^{n-1}`, `curr = u^n` after advancing to step `n`).

## Initial pulse

Gaussian parameters from `/app/fixtures/source_layout.json`. Center at `(gridSize/2, gridSize/2)` in cell coordinates; set both `prev` and `curr` at the pulse interior cells before step 0.

## Output schema (`/app/output_trace.json`)

```json
{
  "gridSize": <int>,
  "steps": <int>,
  "stride": <int>,
  "order": <int>,
  "maxMemoryBytes": <number>,
  "traces": [
    { "step": <int>, "t": <float>, "grid": [<gridSize² floats>] }
  ]
}
```

`maxMemoryBytes` reports peak `process.memoryUsage().heapUsed` during the run. The integrator must stay within a **15 MiB** (15728640 bytes) heap budget. Large workloads may be launched through `/app/run_capped.sh`, which applies an external old-space heap ceiling below the budget; compliance cannot be satisfied by understating `maxMemoryBytes` alone.

## Numeric tolerances

Physical reference comparisons use absolute tolerance `1e-5`.

## Subsystem scope

Sources under `/app/base/`, `/app/core/`, `/app/util/`, `/app/trace/`, and `/app/run_entry.js` implement allocation, stencil update, edge reconciliation, trace capture, and the run loop. Module-level behavior in those components must be correct, not only CLI output. Static or manual output writes are insufficient.
