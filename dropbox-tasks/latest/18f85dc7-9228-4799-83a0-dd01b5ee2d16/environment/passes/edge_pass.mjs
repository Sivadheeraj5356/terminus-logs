export function edge_sel(pack, gridMeta) {
  const peel = Math.ceil(
    gridMeta.boundary_fraction * Math.max(gridMeta.nx, gridMeta.ny, gridMeta.nz),
  );
  // Use predication_cutoff to select edge mode
  const edge_mode = gridMeta.boundary_fraction > pack.predication_cutoff
    ? 'duplicate'
    : 'predicated';
  return {
    edge_mode,
    peel_rows: peel,
    boundary_fraction: gridMeta.boundary_fraction,
  };
}
