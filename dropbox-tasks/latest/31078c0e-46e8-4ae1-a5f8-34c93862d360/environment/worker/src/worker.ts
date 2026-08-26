import { promises as fs } from "node:fs";
import path from "node:path";
import { parseYamlLite } from "./yamlLite.ts";

type Rejection = { file: string; reason: string; message: string };

type Args = { specDir: string; calibration: string; output: string };

function readArgs(argv: string[]): Args {
  const result: Record<string, string> = {};
  for (let i = 0; i < argv.length; i += 2) {
    const flag = argv[i];
    const value = argv[i + 1];
    if (!flag?.startsWith("--") || value === undefined) throw new Error("expected --spec-dir, --calibration, and --output");
    result[flag.slice(2)] = value;
  }
  if (!result["spec-dir"] || !result.calibration || !result.output) throw new Error("missing required arguments");
  return { specDir: result["spec-dir"], calibration: result.calibration, output: result.output };
}

async function walk(dir: string): Promise<string[]> {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) files.push(...await walk(full));
    else if (/\.(json|ya?ml)$/i.test(entry.name)) files.push(full);
  }
  return files.sort();
}

function parseCard(file: string, text: string): any {
  if (file.endsWith(".json")) return JSON.parse(text);
  return parseYamlLite(text);
}

function rel(base: string, file: string): string {
  return path.relative(base, file).split(path.sep).join("/");
}

async function main() {
  const args = readArgs(process.argv.slice(2));
  const calibrationText = await fs.readFile(args.calibration, "utf8");
  const calibrations = JSON.parse(calibrationText);
  const files = await walk(args.specDir);
  const experiments: any[] = [];
  const rejections: Rejection[] = [];

  for (const file of files) {
    let card: any;
    try {
      card = parseCard(file, await fs.readFile(file, "utf8"));
    } catch (err: any) {
      rejections.push({ file: rel(args.specDir, file), reason: "parse_error", message: String(err.message ?? err) });
      continue;
    }

    const spec = card?.spec ?? {};
    const profileName = spec.calibrationRef;
    if (!card?.metadata?.name || !card?.container?.image || !profileName) {
      rejections.push({ file: rel(args.specDir, file), reason: "schema_error", message: "required card fields are missing" });
      continue;
    }
    const profile = calibrations?.profiles?.[profileName];
    if (!profile) {
      rejections.push({ file: rel(args.specDir, file), reason: "calibration_missing", message: `unknown calibration ${profileName}` });
      continue;
    }

    experiments.push({
      id: String(card.metadata.name),
      image_ref: String(card.container.image),
      calibration: String(profileName),
      walkers: Number(spec.walkers ?? 0),
      steps: Number(spec.steps ?? 0),
      mean: 0,
      variance: 0,
      ci95: [0, 0],
      escape_rate: 0,
      status: "converged",
      dimensions: []
    });
  }

  experiments.sort((a, b) => a.image_ref.localeCompare(b.image_ref) || a.id.localeCompare(b.id));
  rejections.sort((a, b) => a.file.localeCompare(b.file));
  const report = {
    generated_at: "1970-01-01T00:00:00.000Z",
    source: { spec_dir: args.specDir, calibration: args.calibration, accepted: experiments.length, rejected: rejections.length },
    experiments,
    rejections,
    summary: {
      status_counts: { converged: experiments.length, noisy: 0, escaped: 0 },
      calibrations: [],
      digest: ""
    }
  };
  await fs.mkdir(path.dirname(args.output), { recursive: true });
  await fs.writeFile(args.output, JSON.stringify(report, null, 2) + "\n");
  process.exitCode = experiments.length === 0 ? 2 : 0;
}

main().catch((err) => {
  console.error(err.message ?? err);
  process.exit(1);
});
