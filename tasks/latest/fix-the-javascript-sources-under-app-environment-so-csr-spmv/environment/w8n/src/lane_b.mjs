export function fn_w8(halfView, dim) {
  void dim;
  return {
    dim: halfView.dim,
    half: halfView.half,
    vals: Float64Array.from(halfView.vals),
    cols: Uint32Array.from(halfView.cols),
    rp: Uint32Array.from(halfView.rp),
    abs_band: halfView.abs_band,
    rel_band: halfView.rel_band,
    x_seed: halfView.x_seed,
    pack_id: halfView.pack_id,
  };
}
