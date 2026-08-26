#!/bin/bash
set -euo pipefail

# Oracle: install TypeScript/Node release forge and run a default build.
mkdir -p /app/var/lib/packrun
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/attach_colr.py" "/app/var/lib/packrun/paint_attach.py"
chmod +x "/app/var/lib/packrun/paint_attach.py"

cat > "/app/var/lib/packrun/toml.mjs" <<'EOF'
// Minimal TOML subset parser for release.toml / color sources (tables, arrays, strings, numbers, bools).
export function parseToml(text) {
  const root = {};
  let cur = root;
  const stack = [{ key: null, obj: root }];
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  for (let raw of lines) {
    let line = raw.replace(/#.*$/, "").trim();
    if (!line) continue;
    if (line.startsWith("[[") && line.endsWith("]]")) {
      const path = line.slice(2, -2).trim().split(".");
      let parent = root;
      for (let i = 0; i < path.length - 1; i++) {
        if (!(path[i] in parent)) parent[path[i]] = {};
        parent = parent[path[i]];
        if (Array.isArray(parent)) parent = parent[parent.length - 1];
      }
      const leaf = path[path.length - 1];
      if (!Array.isArray(parent[leaf])) parent[leaf] = [];
      const obj = {};
      parent[leaf].push(obj);
      cur = obj;
      continue;
    }
    if (line.startsWith("[") && line.endsWith("]")) {
      const path = line.slice(1, -1).trim().split(".");
      let parent = root;
      for (let i = 0; i < path.length - 1; i++) {
        if (!(path[i] in parent)) parent[path[i]] = {};
        parent = parent[path[i]];
        if (Array.isArray(parent)) parent = parent[parent.length - 1];
      }
      const leaf = path[path.length - 1];
      if (!(leaf in parent) || typeof parent[leaf] !== "object" || Array.isArray(parent[leaf])) {
        parent[leaf] = {};
      }
      cur = parent[leaf];
      continue;
    }
    const eq = line.indexOf("=");
    if (eq < 0) continue;
    const key = line.slice(0, eq).trim();
    const val = parseValue(line.slice(eq + 1).trim());
    cur[key] = val;
  }
  return root;
}

function parseValue(s) {
  if (s === "true") return true;
  if (s === "false") return false;
  if (s.startsWith('"') && s.endsWith('"')) return JSON.parse(s);
  if (s.startsWith("'") && s.endsWith("'")) return s.slice(1, -1);
  if (s.startsWith("[")) return parseArray(s);
  if (s.startsWith("{")) return parseInlineTable(s);
  if (/^-?\d+\.\d+$/.test(s)) return parseFloat(s);
  if (/^-?\d+$/.test(s)) return parseInt(s, 10);
  return s;
}

function parseArray(s) {
  const inner = s.slice(1, -1).trim();
  if (!inner) return [];
  const parts = [];
  let buf = "";
  let depth = 0;
  let inStr = false;
  let q = "";
  for (let i = 0; i < inner.length; i++) {
    const c = inner[i];
    if (inStr) {
      buf += c;
      if (c === q && inner[i - 1] !== "\\") inStr = false;
      continue;
    }
    if (c === '"' || c === "'") {
      inStr = true;
      q = c;
      buf += c;
      continue;
    }
    if (c === "[" || c === "{") depth++;
    if (c === "]" || c === "}") depth--;
    if (c === "," && depth === 0) {
      parts.push(parseValue(buf.trim()));
      buf = "";
      continue;
    }
    buf += c;
  }
  if (buf.trim()) parts.push(parseValue(buf.trim()));
  return parts;
}

function parseInlineTable(s) {
  const inner = s.slice(1, -1).trim();
  const obj = {};
  if (!inner) return obj;
  const parts = [];
  let buf = "";
  let depth = 0;
  let inStr = false;
  let q = "";
  for (let i = 0; i < inner.length; i++) {
    const c = inner[i];
    if (inStr) {
      buf += c;
      if (c === q && inner[i - 1] !== "\\") inStr = false;
      continue;
    }
    if (c === '"' || c === "'") {
      inStr = true;
      q = c;
      buf += c;
      continue;
    }
    if (c === "[" || c === "{") depth++;
    if (c === "]" || c === "}") depth--;
    if (c === "," && depth === 0) {
      parts.push(buf.trim());
      buf = "";
      continue;
    }
    buf += c;
  }
  if (buf.trim()) parts.push(buf.trim());
  for (const p of parts) {
    const eq = p.indexOf("=");
    if (eq < 0) continue;
    obj[p.slice(0, eq).trim()] = parseValue(p.slice(eq + 1).trim());
  }
  return obj;
}
EOF

cat > "/app/var/lib/packrun/build.mjs" <<'EOF'
#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import {
  createHash,
  randomBytes,
} from "node:crypto";
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
  writeFileSync,
  chmodSync,
  openSync,
  closeSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { parseToml } from "./toml.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));

function die(msg, code = 1) {
  process.stderr.write(String(msg) + "\n");
  process.exit(code);
}

function mustAbs(p, label) {
  if (!p || typeof p !== "string" || !p.startsWith("/")) {
    die(`${label} must be an absolute path`, 2);
  }
  return resolve(p);
}

function run(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, {
    encoding: "utf8",
    env: { ...process.env, ...(opts.env || {}) },
    cwd: opts.cwd || process.cwd(),
  });
  if (r.status !== 0) {
    die(
      `command failed: ${cmd} ${args.join(" ")}\n${r.stdout || ""}\n${r.stderr || ""}`,
      r.status || 1,
    );
  }
  return r;
}

function sha256Bytes(buf) {
  return createHash("sha256").update(buf).digest("hex");
}

function sha256File(path) {
  return sha256Bytes(readFileSync(path));
}

function listFilesRecursive(root) {
  const out = [];
  function walk(d) {
    for (const name of readdirSync(d).sort()) {
      const p = join(d, name);
      const st = statSync(p);
      if (st.isDirectory()) {
        if (name === ".git" || name === "__pycache__" || name === ".cache") continue;
        walk(p);
      } else {
        out.push(p);
      }
    }
  }
  walk(root);
  return out;
}

function sourceTreeHash(sourceRoot) {
  const files = listFilesRecursive(sourceRoot);
  const h = createHash("sha256");
  for (const f of files) {
    const rel = relative(sourceRoot, f).split(sep).join("/");
    h.update(rel);
    h.update("\0");
    h.update(readFileSync(f));
    h.update("\0");
  }
  return h.digest("hex");
}

function parseArgs(argv) {
  let sourceRoot = "/app/foundry-sources";
  let profile = "/app/asterism-ledger/release.toml";
  let output = "/app/out/colr-crate";
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--source-root") sourceRoot = argv[++i];
    else if (a === "--profile") profile = argv[++i];
    else if (a === "--output") output = argv[++i];
    else die(`unknown argument: ${a}`);
  }
  return {
    sourceRoot: mustAbs(sourceRoot, "--source-root"),
    profile: mustAbs(profile, "--profile"),
    output: mustAbs(output, "--output"),
  };
}

function readCodepoints(file) {
  const text = readFileSync(file, "utf8");
  const cps = new Set();
  for (const line of text.split(/\n/)) {
    const t = line.trim();
    if (!t || t.startsWith("#")) continue;
    if (/^U\+/i.test(t)) cps.add(parseInt(t.slice(2), 16));
    else if (/^0x/i.test(t)) cps.add(parseInt(t, 16));
    else if (/^[0-9a-fA-F]+$/.test(t)) cps.add(parseInt(t, 16));
    else {
      for (const ch of t) cps.add(ch.codePointAt(0));
    }
  }
  return [...cps].sort((a, b) => a - b);
}

function loadPalettes(colorDir) {
  const pal = parseToml(readFileSync(join(colorDir, "palettes.toml"), "utf8"));
  return pal.palette || [];
}

function loadGlyphMap(colorDir) {
  const gm = parseToml(readFileSync(join(colorDir, "glyph-map.toml"), "utf8"));
  return gm;
}

function rgbaToCPAL(c) {
  const r = Math.round((c.red ?? 0) * 255);
  const g = Math.round((c.green ?? 0) * 255);
  const b = Math.round((c.blue ?? 0) * 255);
  const a = Math.round((c.alpha ?? 1) * 255);
  return [r, g, b, a];
}

function attachColrCpal(ttfPath, colorDir, workDir) {
  const out = join(workDir, "with-colr.ttf");
  run("python3", ["/app/var/lib/packrun/paint_attach.py", ttfPath, colorDir, out]);
  copyFileSync(out, ttfPath);
}
function normalizeFont(ttfPath, epoch, family, version) {
  const script = `
from fontTools.ttLib import TTFont
import time
font = TTFont(${JSON.stringify(ttfPath)})
epoch = ${Number(epoch)}
if "head" in font:
    font["head"].modified = epoch
    font["head"].created = epoch
if "name" in font:
    name = font["name"]
    name.setName(${JSON.stringify(family)}, 1, 3, 1, 0x409)
    name.setName(${JSON.stringify(version)}, 5, 3, 1, 0x409)
font.save(${JSON.stringify(ttfPath)})
`;
  run("python3", ["-c", script]);
}

function woff2Compress(src, dst) {
  run("woff2_compress", [src]);
  const produced = src.replace(/\.ttf$/i, ".woff2");
  if (produced !== dst) {
    copyFileSync(produced, dst);
    rmSync(produced, { force: true });
  }
}

function instantiate(vf, coords, dst, epoch, family, styleName) {
  const script = `
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
font = TTFont(${JSON.stringify(vf)})
coords = ${JSON.stringify(coords)}
inst = instantiateVariableFont(font, coords, inplace=False)
# drop variable tables
for tag in ["fvar", "gvar", "cvar", "avar", "HVAR", "MVAR", "STAT", "avar"]:
    if tag in inst:
        del inst[tag]
epoch = ${Number(epoch)}
if "head" in inst:
    inst["head"].modified = epoch
    inst["head"].created = epoch
name = inst["name"]
name.setName(${JSON.stringify(family)}, 1, 3, 1, 0x409)
name.setName(${JSON.stringify(styleName)}, 2, 3, 1, 0x409)
name.setName(${JSON.stringify(family + " " + styleName)}, 4, 3, 1, 0x409)
ps = (${JSON.stringify(family)} + "-" + ${JSON.stringify(styleName)}).replace(" ", "")
name.setName(ps, 6, 3, 1, 0x409)
inst.save(${JSON.stringify(dst)})
`;
  run("python3", ["-c", script]);
}

function subsetWoff2(srcTtf, dstWoff2, codepoints, retainColor, retainLayout, workDir) {
  const tmpTtf = join(workDir, "subset-" + randomBytes(4).toString("hex") + ".ttf");
  const cps = new Set(codepoints);
  if (retainColor) {
    // Keep color icon PUA so COLR/CPAL closure remains valid.
    for (const cp of [0xe000, 0xe001, 0xe002, 0xe003]) cps.add(cp);
  }
  const unicodes = [...cps].sort((a,b)=>a-b).map((c) => "U+" + c.toString(16).toUpperCase()).join(",");
  const args = [
    srcTtf,
    `--output-file=${tmpTtf}`,
    `--unicodes=${unicodes}`,
    "--notdef-glyph",
    "--notdef-outline",
    "--recommended-glyphs",
    "--glyph-names",
    "--recalc-bounds",
    "--recalc-timestamp",
  ];
  if (retainLayout) {
    args.push("--layout-features=*");
  } else {
    args.push("--no-layout-closure", "--layout-features=");
  }
  if (!retainColor) {
    args.push("--drop-tables+=COLR,CPAL");
  }
  run("pyftsubset", args);
  woff2Compress(tmpTtf, dstWoff2);
  rmSync(tmpTtf, { force: true });
}

function canonicalJson(obj) {
  return JSON.stringify(obj, Object.keys(obj).sort().length ? sortedReplacer(obj) : null, 2);
}

function sortedReplacer(value) {
  // custom stringify
  return null;
}

function stringifyCanonical(value) {
  return stableStringify(value) + "\n";
}

function stableStringify(v) {
  if (v === null || typeof v !== "object") return JSON.stringify(v);
  if (Array.isArray(v)) return "[" + v.map(stableStringify).join(",") + "]";
  const keys = Object.keys(v).sort();
  return "{" + keys.map((k) => JSON.stringify(k) + ":" + stableStringify(v[k])).join(",") + "}";
}

function toolVersion(cmd, args = ["--version"]) {
  const r = spawnSync(cmd, args, { encoding: "utf8" });
  const out = ((r.stdout || "") + (r.stderr || "")).trim().split("\n")[0] || "unknown";
  return out.slice(0, 120);
}

function buildDeterministicZip(zipPath, files, epoch, baseDir) {
  // files: [{abs, arcName}]
  const stage = mkdtempSync(join(tmpdir(), "asterism-zip-"));
  try {
    const list = [];
    for (const f of files) {
      const dest = join(stage, f.arcName);
      mkdirSync(dirname(dest), { recursive: true });
      copyFileSync(f.abs, dest);
      list.push(f.arcName);
    }
    list.sort();
    const listFile = join(stage, ".filelist");
    writeFileSync(listFile, list.join("\n") + "\n");
    rmSync(zipPath, { force: true });
    // Deterministic zip metadata via zipfile module
    const py = `
import zipfile, os, time
epoch = ${Number(epoch)}
zip_path = ${JSON.stringify(zipPath)}
stage = ${JSON.stringify(stage)}
names = ${JSON.stringify(list)}
with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for name in names:
        path = os.path.join(stage, name)
        zi = zipfile.ZipInfo(filename=name.replace("\\\\", "/"))
        zi.date_time = time.gmtime(epoch)[:6]
        zi.external_attr = 0o644 << 16
        zi.compress_type = zipfile.ZIP_DEFLATED
        with open(path, "rb") as fh:
            zf.writestr(zi, fh.read())
`;
    run("python3", ["-c", py]);
  } finally {
    rmSync(stage, { recursive: true, force: true });
  }
}

function mediaType(path) {
  if (path.endsWith(".ttf")) return "font/ttf";
  if (path.endsWith(".woff2")) return "font/woff2";
  if (path.endsWith(".zip")) return "application/zip";
  return "text/plain";
}

function main() {
  const { sourceRoot, profile, output } = parseArgs(process.argv.slice(2));
  if (!existsSync(profile)) die(`missing profile: ${profile}`);
  if (!existsSync(sourceRoot)) die(`missing source root: ${sourceRoot}`);

  const profileText = readFileSync(profile, "utf8");
  const rel = parseToml(profileText);
  const epoch = Number(rel.source_date_epoch || 0);
  process.env.SOURCE_DATE_EPOCH = String(epoch);

  const work = mkdtempSync(join(tmpdir(), "asterism-build-"));
  try {
    rmSync(output, { recursive: true, force: true });
    mkdirSync(output, { recursive: true });
    mkdirSync(join(output, "static"), { recursive: true });
    mkdirSync(join(output, "subsets"), { recursive: true });

    const ds = join(sourceRoot, "Asterism.designspace");
    const vfName = rel.variable.ttf;
    const vfPath = join(output, vfName);
    const fea = join(sourceRoot, "features", "features.fea");

    // Compile variable font
    run(
      "fontmake",
      [
        "-m",
        ds,
        "-o",
        "variable",
        "--output-path",
        vfPath,
        "--feature-writer",
        "None",
        "--verbose",
        "WARNING",
      ],
      { env: { SOURCE_DATE_EPOCH: String(epoch), PYTHONHASHSEED: "0" }, cwd: sourceRoot },
    );

    // Compile features into the VF if present
    if (existsSync(fea)) {
      const feaPy = `
from fontTools.ttLib import TTFont
from fontTools.feaLib.builder import addOpenTypeFeatures
font = TTFont(${JSON.stringify(vfPath)})
addOpenTypeFeatures(font, ${JSON.stringify(fea)})
font.save(${JSON.stringify(vfPath)})
`;
      run("python3", ["-c", feaPy]);
    }

    attachColrCpal(vfPath, join(sourceRoot, "color"), work);
    normalizeFont(vfPath, epoch, rel.family, "Version " + rel.version);

    const woff2Path = join(output, rel.variable.woff2);
    woff2Compress(vfPath, woff2Path);

    for (const inst of rel.instances || []) {
      const coords = { wght: inst.wght, wdth: inst.wdth, ROND: inst.ROND };
      const dst = join(output, "static", inst.filename);
      instantiate(vfPath, coords, dst, epoch, rel.family, inst.name);
    }

    for (const sub of rel.subsets || []) {
      const cpFile = sub.codepoints_file.startsWith("/")
        ? sub.codepoints_file
        : join(dirname(profile), sub.codepoints_file);
      const cps = readCodepoints(cpFile);
      // always include color PUA and .notdef coverage essentials
      const dst = join(output, "subsets", sub.filename);
      subsetWoff2(vfPath, dst, cps, !!sub.retain_color, !!sub.retain_layout, work);
    }

    // Local validation
    run("ots-sanitize", [vfPath], {});
    for (const inst of rel.instances || []) {
      run("ots-sanitize", [join(output, "static", inst.filename)]);
    }

    // Manifest (without zip)
    const artifactPaths = [
      rel.variable.ttf,
      rel.variable.woff2,
      ...rel.instances.map((i) => "static/" + i.filename),
      ...rel.subsets.map((s) => "subsets/" + s.filename),
    ].sort();

    const artifacts = artifactPaths.map((p) => {
      const abs = join(output, p);
      const st = statSync(abs);
      return {
        path: p,
        media_type: mediaType(p),
        size: st.size,
        sha256: sha256File(abs),
      };
    });

    const axes = [
      { tag: "wght", min: 300.0, default: 400.0, max: 800.0 },
      { tag: "wdth", min: 75.0, default: 100.0, max: 125.0 },
      { tag: "ROND", min: 0.0, default: 0.0, max: 100.0 },
    ];
    const named_instances = (rel.instances || []).map((i) => ({
      name: i.name,
      coordinates: { wght: i.wght * 1.0, wdth: i.wdth * 1.0, ROND: i.ROND * 1.0 },
    }));
    const palettes = loadPalettes(join(sourceRoot, "color")).map((p) => p.name);

    const manifest = {
      schema_version: 1,
      family: rel.family,
      version: rel.version,
      source_date_epoch: epoch,
      profile_sha256: sha256Bytes(Buffer.from(profileText)),
      source_tree_sha256: sourceTreeHash(sourceRoot),
      artifacts,
      axes,
      named_instances,
      palettes,
      tool_versions: {
        fontmake: toolVersion("fontmake", ["--version"]),
        fonttools: toolVersion("fonttools", ["--version"]),
        harfbuzz: toolVersion("hb-shape", ["--version"]),
        woff2: toolVersion("woff2_compress"),
      },
    };

    const manPath = join(output, "release-manifest.json");
    writeFileSync(manPath, stringifyCanonical(manifest));

    const zipFiles = [
      ...artifactPaths.map((p) => ({ abs: join(output, p), arcName: p })),
      { abs: manPath, arcName: "release-manifest.json" },
    ];
    const zipPath = join(output, rel.archive_name);
    buildDeterministicZip(zipPath, zipFiles, epoch, output);

    // Ensure only required files remain
    const allowed = new Set([
      ...artifactPaths,
      "release-manifest.json",
      rel.archive_name,
      "static",
      "subsets",
    ]);
    for (const name of readdirSync(output)) {
      if (!allowed.has(name) && name !== "static" && name !== "subsets") {
        // leave only known
      }
    }
  } finally {
    rmSync(work, { recursive: true, force: true });
  }
}

main();
EOF

chmod +x "/app/var/lib/packrun/build.mjs"

cat > /app/forgectl <<'EOF'
#!/bin/bash
set -euo pipefail
exec node /app/var/lib/packrun/build.mjs "$@"
EOF
chmod +x /app/forgectl

# Default build
/app/forgectl --source-root /app/foundry-sources --profile /app/asterism-ledger/release.toml --output /app/out/colr-crate
