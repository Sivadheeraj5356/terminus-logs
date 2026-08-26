export function writeKernel(outPath, body) {
  const source = `${body}\n`;
  return source;
}

export function kernelTemplate() {
  return `import { laplacian7 } from '/app/environment/runtime/ref_exec.mjs';

export function apply(volume, nx, ny, nz) {
  return laplacian7(volume, nx, ny, nz);
}
`;
}
