import { createReadStream } from "node:fs";
import { mkdir, readdir, rename, rm, stat } from "node:fs/promises";
import { join } from "node:path";
import * as tar from "tar";
import { loadPolicyRules } from "./policyBridge.mjs";

export async function extractBundle(bundlePath, stagingRoot) {
  await mkdir(stagingRoot, { recursive: true });
  await tar.extract({
    file: bundlePath,
    cwd: stagingRoot,
  });

  const rules = loadPolicyRules();
  if (rules.ARCHIVE_STRIP_PREFIX === "first_segment") {
    const homesDir = join(stagingRoot, "homes");
    try {
      const entries = await readdir(homesDir);
      for (const entry of entries) {
        await rename(join(homesDir, entry), join(stagingRoot, entry));
      }
      await rm(homesDir, { recursive: true, force: true });
    } catch {
      // ignore missing homes dir
    }
  }
}

export async function fileModeAt(root, relativePath) {
  const full = join(root, relativePath);
  const st = await stat(full);
  return (st.mode & 0o7777).toString(8);
}
