import { mkdir } from "node:fs/promises";
import * as tar from "tar";

export async function extractBundle(bundlePath, stagingRoot) {
  await mkdir(stagingRoot, { recursive: true });
  await tar.extract({
    file: bundlePath,
    cwd: stagingRoot,
  });
}

export async function fileModeAt(root, relativePath) {
  const { join } = await import("node:path");
  const { stat } = await import("node:fs/promises");
  const full = join(root, relativePath);
  const st = await stat(full);
  return (st.mode & 0o7777).toString(8);
}
