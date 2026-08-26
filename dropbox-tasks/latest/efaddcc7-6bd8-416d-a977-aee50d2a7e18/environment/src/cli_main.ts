import * as path from "path";
import { runCases } from "../tools/cli_runner";

function argValue(flag: string): string | null {
  const idx = process.argv.indexOf(flag);
  if (idx < 0 || idx + 1 >= process.argv.length) {
    return null;
  }
  return process.argv[idx + 1];
}

const casesPath = argValue("--cases");
if (!casesPath) {
  console.error("usage: npm run play -- --cases /app/fixtures/cases.toml");
  process.exit(2);
}

const outDir = path.resolve("/app/output");
runCases(path.resolve(casesPath), outDir);
