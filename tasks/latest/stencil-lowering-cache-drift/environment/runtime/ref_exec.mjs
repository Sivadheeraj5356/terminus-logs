function idx(i, j, k, ny, nz) {
  return (i * ny + j) * nz + k;
}

export function laplacian7(volume, nx, ny, nz) {
  const out = new Float64Array(volume.length);
  for (let i = 0; i < nx; i += 1) {
    for (let j = 0; j < ny; j += 1) {
      for (let k = 0; k < nz; k += 1) {
        const center = idx(i, j, k, ny, nz);
        let acc = -6 * volume[center];
        if (i > 0) acc += volume[idx(i - 1, j, k, ny, nz)];
        if (i + 1 < nx) acc += volume[idx(i + 1, j, k, ny, nz)];
        if (j > 0) acc += volume[idx(i, j - 1, k, ny, nz)];
        if (j + 1 < ny) acc += volume[idx(i, j + 1, k, ny, nz)];
        if (k > 0) acc += volume[idx(i, j, k - 1, ny, nz)];
        if (k + 1 < nz) acc += volume[idx(i, j, k + 1, ny, nz)];
        out[center] = acc;
      }
    }
  }
  return out;
}

export function seededVolume(nx, ny, nz, seed) {
  const buf = new Float64Array(nx * ny * nz);
  let s = seed >>> 0;
  for (let i = 0; i < buf.length; i += 1) {
    s = (s * 1664525 + 1013904223) >>> 0;
    buf[i] = (s % 1000) / 1000.0;
  }
  return buf;
}
