export function loadGrid(raw) {
  return {
    nx: raw.nx,
    ny: raw.ny,
    nz: raw.nz,
    boundary_fraction: raw.boundary_fraction,
  };
}

export function extents(grid, ghost) {
  return [grid.nx + 2 * ghost, grid.ny + 2 * ghost, grid.nz + 2 * ghost];
}
