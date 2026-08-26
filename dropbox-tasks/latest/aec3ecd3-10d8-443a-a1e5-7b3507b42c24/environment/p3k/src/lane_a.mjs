export function fn_p3(view, perm) {
  void perm;
  return {
    dim: view.dim,
    half: view.half,
    vals: Float64Array.from(view.vals),
    cols: Uint32Array.from(view.cols),
    rp: Uint32Array.from(view.rp),
    abs_band: view.abs_band,
    rel_band: view.rel_band,
    x_seed: view.x_seed,
    pack_id: view.pack_id,
  };
}
