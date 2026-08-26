export function retile_op(pack, halo, capBytes) {
  const tile = pack.tile.slice();
  const elem = 8; // 8 bytes per double
  const volume = tile.reduce((acc, dim) => acc * (dim + 2 * halo), 1);
  const scratch = volume * elem;
  return {
    tile,
    scratch_peak: Math.min(scratch, capBytes),
    temporal: pack.temporal_tiling,
  };
}
