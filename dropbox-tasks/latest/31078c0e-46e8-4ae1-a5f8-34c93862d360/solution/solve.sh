#!/usr/bin/env bash
cat > /app/worker/src/yamlLite.ts <<'TSY'
type Frame = { indent: number; container: any; key?: string };

function scalar(text: string): any {
  const value = text.trim();
  if (value === "") return "";
  if (value === "null" || value === "~") return null;
  if (value === "true") return true;
  if (value === "false") return false;
  if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) return value.slice(1, -1);
  if (/^-?\d+(\.\d+)?([eE][+-]?\d+)?$/.test(value)) return Number(value);
  return value;
}

function splitKeyValue(text: string): [string, string] {
  const idx = text.indexOf(":");
  if (idx < 0) throw new Error("YAML line is missing ':'");
  return [text.slice(0, idx).trim(), text.slice(idx + 1).trim()];
}

function stripComment(line: string): string {
  let quote: string | null = null;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if ((ch === '"' || ch === "'") && line[i - 1] !== "\\") quote = quote === ch ? null : quote ?? ch;
    if (ch === "#" && quote === null) return line.slice(0, i);
  }
  return line;
}

export function parseYamlLite(text: string): any {
  const root: any = {};
  const stack: Frame[] = [{ indent: -1, container: root }];
  const rawLines = text.replace(/\r\n/g, "\n").split("\n");
  const listKeys = new Set(["dimensions", "dependsOn"]);
  for (const rawLine of rawLines) {
    const line = stripComment(rawLine).replace(/\s+$/, "");
    if (!line.trim()) continue;
    const indent = line.length - line.trimStart().length;
    const content = line.trimStart();
    while (stack.length > 1 && indent <= stack[stack.length - 1].indent) stack.pop();
    const parent = stack[stack.length - 1].container;
    if (content.startsWith("- ")) {
      if (!Array.isArray(parent)) throw new Error("YAML list item without list parent");
      const rest = content.slice(2).trim();
      if (!rest) {
        const obj: any = {};
        parent.push(obj);
        stack.push({ indent, container: obj });
      } else if (rest.includes(":")) {
        const [key, value] = splitKeyValue(rest);
        const obj: any = {};
        obj[key] = value === "" ? {} : scalar(value);
        parent.push(obj);
        stack.push({ indent, container: value === "" ? obj[key] : obj });
      } else parent.push(scalar(rest));
      continue;
    }
    const [key, value] = splitKeyValue(content);
    if (value === "") {
      const child: any = listKeys.has(key) ? [] : {};
      parent[key] = child;
      stack.push({ indent, container: child, key });
    } else parent[key] = scalar(value);
  }
  return root;
}
TSY
cat > /app/worker/src/worker.ts <<'TS'
import { createHash } from "node:crypto";
import { promises as fs } from "node:fs";
import path from "node:path";
import { parseYamlLite } from "./yamlLite.ts";

type Args = { specDir: string; calibration: string; output: string };
type RejectionReason = "parse_error" | "schema_error" | "range_error" | "calibration_missing" | "dependency_missing" | "dependency_cycle" | "superseded" | "retention_excluded";
type Rejection = { file: string; reason: RejectionReason; message: string };
type Adjustment = { weightScale?: number; weightBias?: number; lowerShift?: number; upperShift?: number };
type Retention = { maxExperiments: number; riskWindow: number };
type Profile = {
  inherits?: string;
  driftScale?: number;
  volatilityScale?: number;
  driftBias?: number;
  confidenceK?: number;
  ciLimit?: number;
  escapeThreshold?: number;
  dependencyAttenuation?: number;
  dimensionAdjustments?: Record<string, Adjustment>;
  retention?: Retention;
};
type ResolvedProfile = Required<Pick<Profile, "driftScale" | "volatilityScale" | "driftBias" | "confidenceK" | "ciLimit" | "escapeThreshold" | "dependencyAttenuation">> & {
  dimensionAdjustments?: Record<string, Adjustment>;
  retention?: Retention;
};
type Dimension = { name: string; weight: number; lower: number; upper: number };

const STATUS_KEYS = ["converged", "noisy", "escaped"] as const;
const STATUS_RANK: Record<string, number> = { converged: 0, noisy: 1, escaped: 2 };
const ADJUSTMENT_FIELDS = new Set(["weightScale", "weightBias", "lowerShift", "upperShift"]);

function readArgs(argv: string[]): Args {
  const values: Record<string, string> = {};
  for (let i = 0; i < argv.length; i++) {
    const flag = argv[i];
    if (!flag.startsWith("--")) throw new Error(`unexpected argument ${flag}`);
    const value = argv[++i];
    if (value === undefined) throw new Error(`missing value for ${flag}`);
    values[flag.slice(2)] = value;
  }
  if (!values["spec-dir"] || !values.calibration || !values.output) {
    throw new Error("expected --spec-dir, --calibration, and --output");
  }
  return { specDir: values["spec-dir"], calibration: values.calibration, output: values.output };
}

async function listCards(root: string): Promise<string[]> {
  const out: string[] = [];
  async function visit(dir: string): Promise<void> {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    entries.sort((a, b) => a.name.localeCompare(b.name));
    for (const entry of entries) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) await visit(full);
      else if (/\.(json|ya?ml)$/i.test(entry.name)) out.push(full);
    }
  }
  await visit(root);
  return out.sort((a, b) => relativeName(root, a).localeCompare(relativeName(root, b)));
}

function relativeName(root: string, file: string): string {
  return path.relative(root, file).split(path.sep).join("/");
}

async function readCard(file: string): Promise<any> {
  const text = await fs.readFile(file, "utf8");
  if (file.toLowerCase().endsWith(".json")) return JSON.parse(text);
  return parseYamlLite(text);
}

function isObject(value: any): value is Record<string, any> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isFiniteNumber(value: any): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isInteger(value: any): value is number {
  return Number.isInteger(value);
}

function validateAdjustment(value: any): value is Adjustment {
  if (!isObject(value)) return false;
  for (const [key, fieldValue] of Object.entries(value)) {
    if (!ADJUSTMENT_FIELDS.has(key) || !isFiniteNumber(fieldValue)) return false;
  }
  return true;
}

function validateRetention(value: any): value is Retention {
  return isObject(value)
    && Object.keys(value).every((key) => key === "maxExperiments" || key === "riskWindow")
    && isInteger(value.maxExperiments)
    && value.maxExperiments > 0
    && isFiniteNumber(value.riskWindow)
    && value.riskWindow >= 0;
}

function validateRawProfile(profile: any): profile is Profile {
  if (!isObject(profile)) return false;
  if ("inherits" in profile && (typeof profile.inherits !== "string" || profile.inherits.length === 0)) return false;
  for (const field of ["driftScale", "volatilityScale", "driftBias", "confidenceK", "ciLimit", "escapeThreshold", "dependencyAttenuation"]) {
    if (field in profile && !isFiniteNumber(profile[field])) return false;
  }
  if ("dimensionAdjustments" in profile) {
    if (!isObject(profile.dimensionAdjustments)) return false;
    for (const [key, value] of Object.entries(profile.dimensionAdjustments)) {
      if (typeof key !== "string" || !validateAdjustment(value)) return false;
    }
  }
  if ("retention" in profile && !validateRetention(profile.retention)) return false;
  return true;
}

function mergeAdjustments(parent: Record<string, Adjustment> | undefined, child: Record<string, Adjustment> | undefined): Record<string, Adjustment> | undefined {
  if (!parent && !child) return undefined;
  const merged: Record<string, Adjustment> = {};
  for (const [key, value] of Object.entries(parent ?? {})) merged[key] = { ...value };
  for (const [key, value] of Object.entries(child ?? {})) merged[key] = { ...(merged[key] ?? {}), ...value };
  return merged;
}

function resolveProfile(calibrations: any, name: string, stack: string[] = []): ResolvedProfile | undefined {
  const profiles = calibrations?.profiles;
  if (!isObject(profiles) || !(name in profiles) || stack.includes(name)) return undefined;
  const raw = profiles[name];
  if (!validateRawProfile(raw)) return undefined;
  let merged: any = {};
  if (raw.inherits !== undefined) {
    const parent = resolveProfile(calibrations, raw.inherits, [...stack, name]);
    if (!parent) return undefined;
    merged = JSON.parse(JSON.stringify(parent));
  }
  for (const field of ["driftScale", "volatilityScale", "driftBias", "confidenceK", "ciLimit", "escapeThreshold", "dependencyAttenuation"]) {
    if (field in raw) merged[field] = raw[field];
  }
  if ("dimensionAdjustments" in raw) merged.dimensionAdjustments = mergeAdjustments(merged.dimensionAdjustments, raw.dimensionAdjustments);
  if ("retention" in raw) merged.retention = { ...(merged.retention ?? {}), ...raw.retention };
  for (const field of ["driftScale", "volatilityScale", "driftBias", "confidenceK", "ciLimit", "escapeThreshold", "dependencyAttenuation"]) {
    if (!isFiniteNumber(merged[field])) return undefined;
  }
  if (merged.dependencyAttenuation < 0 || merged.dependencyAttenuation > 1) return undefined;
  if ("dimensionAdjustments" in merged) {
    if (!isObject(merged.dimensionAdjustments)) return undefined;
    for (const value of Object.values(merged.dimensionAdjustments)) if (!validateAdjustment(value)) return undefined;
  }
  if ("retention" in merged && !validateRetention(merged.retention)) return undefined;
  return merged as ResolvedProfile;
}

function validate(card: any, calibrations: any): { reason?: RejectionReason; message?: string; profile?: ResolvedProfile } {
  if (!isObject(card)) return { reason: "schema_error", message: "card must be an object" };
  if (card.apiVersion !== "diffusion.ops/v1" || card.kind !== "DiffusionExperiment") {
    return { reason: "schema_error", message: "apiVersion or kind is not supported" };
  }
  if (!isObject(card.metadata) || typeof card.metadata.name !== "string" || card.metadata.name.length === 0) {
    return { reason: "schema_error", message: "metadata.name is required" };
  }
  if ("revision" in card.metadata && !isInteger(card.metadata.revision)) {
    return { reason: "schema_error", message: "metadata.revision must be an integer" };
  }
  if (!isObject(card.container) || typeof card.container.image !== "string" || card.container.image.length === 0) {
    return { reason: "schema_error", message: "container.image is required" };
  }
  if ("digest" in card.container && typeof card.container.digest !== "string") {
    return { reason: "schema_error", message: "container.digest must be a string" };
  }
  const spec = card.spec;
  if (!isObject(spec)) return { reason: "schema_error", message: "spec is required" };
  for (const field of ["seed", "walkers", "steps"]) {
    if (!isInteger(spec[field])) return { reason: "schema_error", message: `${field} must be an integer` };
  }
  for (const field of ["drift", "volatility"]) {
    if (!isFiniteNumber(spec[field])) return { reason: "schema_error", message: `${field} must be numeric` };
  }
  if (typeof spec.calibrationRef !== "string" || spec.calibrationRef.length === 0) {
    return { reason: "schema_error", message: "calibrationRef is required" };
  }
  if ("dependsOn" in spec) {
    if (!Array.isArray(spec.dependsOn)
      || !spec.dependsOn.every((item: any) => typeof item === "string" && item.length > 0)
      || new Set(spec.dependsOn).size !== spec.dependsOn.length) {
      return { reason: "schema_error", message: "dependsOn must be unique non-empty strings" };
    }
  }
  if (!Array.isArray(spec.dimensions) || spec.dimensions.length === 0) {
    return { reason: "schema_error", message: "dimensions must be a non-empty array" };
  }
  for (const dim of spec.dimensions) {
    if (!isObject(dim) || typeof dim.name !== "string" || dim.name.length === 0) {
      return { reason: "schema_error", message: "dimension.name is required" };
    }
    for (const field of ["weight", "lower", "upper"]) {
      if (!isFiniteNumber(dim[field])) return { reason: "schema_error", message: `dimension.${field} must be numeric` };
    }
  }
  if ((card.metadata.revision ?? 0) < 0) return { reason: "range_error", message: "metadata.revision must be non-negative" };
  if (spec.seed < 1 || spec.seed > 2147483646) return { reason: "range_error", message: "seed is outside the Park-Miller range" };
  if (spec.walkers <= 0 || spec.steps <= 0) return { reason: "range_error", message: "walkers and steps must be positive" };
  if (spec.volatility < 0) return { reason: "range_error", message: "volatility must be non-negative" };
  for (const dim of spec.dimensions) {
    if (!(dim.lower < dim.upper)) return { reason: "range_error", message: "dimension lower must be below upper" };
  }
  const profile = resolveProfile(calibrations, spec.calibrationRef);
  if (!profile) return { reason: "calibration_missing", message: `unknown or malformed calibration ${spec.calibrationRef}` };
  return { profile };
}

function round6(value: number): number {
  const scaled = value * 1_000_000;
  return (scaled >= 0 ? Math.floor(scaled + 0.5) : Math.ceil(scaled - 0.5)) / 1_000_000;
}

function normalizeImage(image: string, digest: string | undefined): string {
  if (!digest) return image;
  const lastSlash = image.lastIndexOf("/");
  const lastColon = image.lastIndexOf(":");
  const base = lastColon > lastSlash ? image.slice(0, lastColon) : image;
  return `${base}@${digest}`;
}

function applyAdjustment(dim: Dimension, adjustment: Adjustment | undefined): Dimension {
  if (!adjustment) return dim;
  return {
    name: dim.name,
    weight: dim.weight * (adjustment.weightScale ?? 1) + (adjustment.weightBias ?? 0),
    lower: dim.lower + (adjustment.lowerShift ?? 0),
    upper: dim.upper + (adjustment.upperShift ?? 0)
  };
}

function effectiveDimensions(card: any, profile: ResolvedProfile): Dimension[] {
  const adjustments = profile.dimensionAdjustments ?? {};
  return card.spec.dimensions.map((raw: Dimension) => {
    let dim: Dimension = { name: raw.name, weight: raw.weight, lower: raw.lower, upper: raw.upper };
    dim = applyAdjustment(dim, adjustments["*"]);
    dim = applyAdjustment(dim, adjustments[raw.name]);
    return dim;
  }).sort((a: Dimension, b: Dimension) => a.name.localeCompare(b.name));
}

class ParkMiller {
  state: number;
  constructor(seed: number) { this.state = seed; }
  uniform(): number {
    this.state = (this.state * 48271) % 2147483647;
    return this.state / 2147483647;
  }
}

function population(values: number[]): { mean: number; variance: number } {
  const mean = values.reduce((acc, value) => acc + value, 0) / values.length;
  const variance = values.reduce((acc, value) => acc + (value - mean) ** 2, 0) / values.length;
  return { mean, variance };
}

function simulate(card: any, profile: ResolvedProfile, file: string): any {
  const spec = card.spec;
  const dimensions = effectiveDimensions(card, profile);
  const drift = spec.drift * profile.driftScale + profile.driftBias;
  const volatility = spec.volatility * profile.volatilityScale;
  const rng = new ParkMiller(spec.seed);
  const scores: number[] = [];
  const finalByDimension = new Map<string, number[]>();
  const escapedByDimension = new Map<string, number>();
  for (const dim of dimensions) {
    finalByDimension.set(dim.name, []);
    escapedByDimension.set(dim.name, 0);
  }
  let escapedWalkers = 0;
  for (let walker = 0; walker < spec.walkers; walker++) {
    const positions = new Map<string, number>();
    const escaped = new Map<string, boolean>();
    for (const dim of dimensions) {
      positions.set(dim.name, 0);
      escaped.set(dim.name, false);
    }
    for (let step = 0; step < spec.steps; step++) {
      for (const dim of dimensions) {
        const uniform = rng.uniform();
        const delta = drift * dim.weight + volatility * (uniform * 2 - 1) * Math.abs(dim.weight);
        const next = (positions.get(dim.name) ?? 0) + delta;
        positions.set(dim.name, next);
        if (next < dim.lower || next > dim.upper) escaped.set(dim.name, true);
      }
    }
    if ([...escaped.values()].some(Boolean)) escapedWalkers += 1;
    let score = 0;
    for (const dim of dimensions) {
      const finalPosition = positions.get(dim.name) ?? 0;
      score += finalPosition;
      finalByDimension.get(dim.name)!.push(finalPosition);
      if (escaped.get(dim.name)) escapedByDimension.set(dim.name, (escapedByDimension.get(dim.name) ?? 0) + 1);
    }
    scores.push(score);
  }
  const scoreStats = population(scores);
  const half = profile.confidenceK * Math.sqrt(scoreStats.variance / spec.walkers);
  const escapeRate = escapedWalkers / spec.walkers;
  const status = escapeRate > profile.escapeThreshold ? "escaped" : ((half * 2) > profile.ciLimit ? "noisy" : "converged");
  const riskScore = round6(STATUS_RANK[status] * 100 + escapeRate * 50 + Math.max(0, half * 2 - profile.ciLimit) * 10 + Math.abs(scoreStats.mean));
  return {
    file,
    id: card.metadata.name,
    revision: card.metadata.revision ?? 0,
    image_ref: normalizeImage(card.container.image, card.container.digest),
    calibration: spec.calibrationRef,
    walkers: spec.walkers,
    steps: spec.steps,
    mean: round6(scoreStats.mean),
    variance: round6(scoreStats.variance),
    ci95: [round6(scoreStats.mean - half), round6(scoreStats.mean + half)],
    escape_rate: round6(escapeRate),
    status,
    risk_score: riskScore,
    dependency_risk: riskScore,
    dependencies: [...(spec.dependsOn ?? [])].sort(),
    dimensions: dimensions.map((dim) => {
      const stats = population(finalByDimension.get(dim.name)!);
      return {
        name: dim.name,
        weight: round6(dim.weight),
        mean: round6(stats.mean),
        variance: round6(stats.variance),
        escape_rate: round6((escapedByDimension.get(dim.name) ?? 0) / spec.walkers)
      };
    })
  };
}


function findCycle(candidateMap: Map<string, any>, marks: Map<string, RejectionReason>): Set<string> {
  const state = new Map<string, number>();
  const stack: string[] = [];
  function visit(name: string): Set<string> {
    state.set(name, 1);
    stack.push(name);
    for (const dep of candidateMap.get(name).dependencies) {
      if (marks.has(dep) || !candidateMap.has(dep)) continue;
      if (state.get(dep) === 1) return new Set(stack.slice(stack.indexOf(dep)));
      if ((state.get(dep) ?? 0) === 0) {
        const found = visit(dep);
        if (found.size > 0) return found;
      }
    }
    stack.pop();
    state.set(name, 2);
    return new Set();
  }
  for (const name of [...candidateMap.keys()].sort()) {
    if (!marks.has(name) && (state.get(name) ?? 0) === 0) {
      const found = visit(name);
      if (found.size > 0) return found;
    }
  }
  return new Set();
}

function applyDependencies(candidates: any[], calibrations: any, rejections: Rejection[]): any[] {
  const byId = new Map<string, any[]>();
  for (const candidate of candidates) byId.set(candidate.id, [...(byId.get(candidate.id) ?? []), candidate]);
  const candidateMap = new Map<string, any>();
  for (const [id, rows] of byId.entries()) if (rows.length === 1) candidateMap.set(id, rows[0]);
  const marks = new Map<string, RejectionReason>();
  for (const candidate of candidates) {
    if (!candidateMap.has(candidate.id) || candidate.dependencies.some((dep: string) => !candidateMap.has(dep))) {
      marks.set(candidate.id, "dependency_missing");
    }
  }
  while (true) {
    let changed = false;
    for (const [id, candidate] of candidateMap.entries()) {
      if (!marks.has(id) && candidate.dependencies.some((dep: string) => marks.has(dep))) {
        marks.set(id, "dependency_missing");
        changed = true;
      }
    }
    const cycle = findCycle(candidateMap, marks);
    if (cycle.size > 0) {
      for (const id of cycle) {
        if (!marks.has(id)) {
          marks.set(id, "dependency_cycle");
          changed = true;
        }
      }
    }
    if (!changed) break;
  }
  const survivors: any[] = [];
  for (const candidate of candidates) {
    const reason = marks.get(candidate.id);
    if (reason) rejections.push({ file: candidate.file, reason, message: `dependency graph rejected ${candidate.id}` });
    else survivors.push(candidate);
  }
  const survivorMap = new Map(survivors.map((candidate) => [candidate.id, candidate]));
  const done = new Set<string>();
  function compute(id: string): void {
    if (done.has(id)) return;
    const row = survivorMap.get(id)!;
    for (const dep of row.dependencies) compute(dep);
    const maxDep = row.dependencies.reduce((acc: number, dep: string) => Math.max(acc, survivorMap.get(dep)!.dependency_risk), 0);
    const profile = resolveProfile(calibrations, row.calibration)!;
    row.dependency_risk = round6(row.risk_score + profile.dependencyAttenuation * maxDep);
    done.add(id);
  }
  for (const id of [...survivorMap.keys()].sort()) compute(id);
  return survivors;
}


function reduceCandidates(candidates: any[], rejections: Rejection[]): any[] {
  const groups = new Map<string, any[]>();
  for (const candidate of candidates) {
    const key = `${candidate.image_ref}\u0000${candidate.calibration}`;
    groups.set(key, [...(groups.get(key) ?? []), candidate]);
  }
  const retained: any[] = [];
  for (const rows of groups.values()) {
    rows.sort((a, b) => (b.dependency_risk - a.dependency_risk)
      || (b.revision - a.revision)
      || a.id.localeCompare(b.id)
      || a.file.localeCompare(b.file));
    const winner = rows[0];
    retained.push(winner);
    for (const loser of rows.slice(1)) {
      rejections.push({ file: loser.file, reason: "superseded", message: `superseded by ${winner.file}` });
    }
  }
  return retained;
}

function applyRetention(experiments: any[], calibrations: any, rejections: Rejection[]): any[] {
  const groups = new Map<string, any[]>();
  for (const experiment of experiments) {
    groups.set(experiment.calibration, [...(groups.get(experiment.calibration) ?? []), experiment]);
  }
  const kept: any[] = [];
  for (const [calibration, rows] of groups.entries()) {
    const profile = resolveProfile(calibrations, calibration);
    const retention = profile?.retention;
    if (!retention) {
      kept.push(...rows);
      continue;
    }
    rows.sort((a, b) => (b.dependency_risk - a.dependency_risk)
      || (b.revision - a.revision)
      || a.id.localeCompare(b.id)
      || a.file.localeCompare(b.file));
    const topRisk = rows[0].dependency_risk;
    for (let index = 0; index < rows.length; index++) {
      const row = rows[index];
      if (index < retention.maxExperiments || topRisk - row.dependency_risk <= retention.riskWindow) {
        kept.push(row);
      } else {
        rejections.push({ file: row.file, reason: "retention_excluded", message: `excluded by retention policy for ${calibration}` });
      }
    }
  }
  return kept;
}

function stable(value: any): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map((item) => stable(item)).join(",")}]`;
  const keys = Object.keys(value).sort();
  return `{${keys.map((key) => `${JSON.stringify(key)}:${stable(value[key])}`).join(",")}}`;
}

function digestFor(experiments: any[], rejections: Rejection[], statusCounts: Record<string, number>, calibrations: any[]): string {
  const digestRejections = rejections.map((row) => ({ file: row.file, reason: row.reason }));
  const payload = { experiments, rejections: digestRejections, status_counts: statusCounts, calibrations };
  return createHash("sha256").update(stable(payload), "utf8").digest("hex");
}

async function main(): Promise<void> {
  const args = readArgs(process.argv.slice(2));
  const calibrations = JSON.parse(await fs.readFile(args.calibration, "utf8"));
  const files = await listCards(args.specDir);
  const candidates: any[] = [];
  const rejections: Rejection[] = [];
  for (const file of files) {
    const displayFile = relativeName(args.specDir, file);
    let card: any;
    try {
      card = await readCard(file);
    } catch (error: any) {
      rejections.push({ file: displayFile, reason: "parse_error", message: String(error?.message ?? error) });
      continue;
    }
    const checked = validate(card, calibrations);
    if (checked.reason) {
      rejections.push({ file: displayFile, reason: checked.reason, message: checked.message ?? checked.reason });
      continue;
    }
    candidates.push(simulate(card, checked.profile!, displayFile));
  }
  const dependencyReady = applyDependencies(candidates, calibrations, rejections);
  const experiments = applyRetention(reduceCandidates(dependencyReady, rejections), calibrations, rejections);
  experiments.sort((a, b) => a.image_ref.localeCompare(b.image_ref) || a.id.localeCompare(b.id));
  rejections.sort((a, b) => a.file.localeCompare(b.file));
  const statusCounts: Record<string, number> = { converged: 0, noisy: 0, escaped: 0 };
  for (const experiment of experiments) statusCounts[experiment.status] += 1;
  const calibrationNames = [...new Set(experiments.map((experiment) => experiment.calibration))].sort();
  const calibrationRows = calibrationNames.map((name) => {
    const rows = experiments.filter((experiment) => experiment.calibration === name);
    const meanEscape = rows.reduce((acc, row) => acc + row.escape_rate, 0) / rows.length;
    const meanDependencyRisk = rows.reduce((acc, row) => acc + row.dependency_risk, 0) / rows.length;
    return { name, experiments: rows.length, mean_escape_rate: round6(meanEscape), mean_dependency_risk: round6(meanDependencyRisk) };
  });
  const summary = {
    status_counts: statusCounts,
    calibrations: calibrationRows,
    digest: digestFor(experiments, rejections, statusCounts, calibrationRows)
  };
  const report = {
    generated_at: "1970-01-01T00:00:00.000Z",
    source: { spec_dir: args.specDir, calibration: args.calibration, accepted: experiments.length, rejected: rejections.length },
    experiments,
    rejections,
    summary
  };
  await fs.mkdir(path.dirname(args.output), { recursive: true });
  await fs.writeFile(args.output, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  process.exitCode = experiments.length === 0 ? 2 : 0;
}

main().catch((error) => {
  console.error(error?.message ?? error);
  process.exit(1);
});
TS
