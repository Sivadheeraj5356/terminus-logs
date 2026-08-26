export function loadPack(raw) {
  return {
    id: raw.id,
    grid_fixture: raw.grid_fixture,
    spill_budget: raw.spill_budget,
    predication_cutoff: raw.predication_cutoff,
    scratch_cap_bytes: raw.scratch_cap_bytes,
    temporal_tiling: Boolean(raw.temporal_tiling),
    tile: raw.tile.slice(),
  };
}
