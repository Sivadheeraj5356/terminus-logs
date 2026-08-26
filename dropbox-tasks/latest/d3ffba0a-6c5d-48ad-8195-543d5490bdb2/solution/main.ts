// RFC 6570 URI Template expansion (Level 4).
//
// Reads a JSON object {"template": <string>, "variables": <object>} from stdin.
// Writes the expanded template string to stdout. On a syntactically invalid
// template, writes "ERROR" and exits with a non-zero status.

import * as fs from "fs";

type JsonValue = string | number | boolean | null | JsonValue[] | JsonObject;
interface JsonObject {
  [k: string]: JsonValue;
}

// --- operator table ------------------------------------------------------

interface OpInfo {
  first: string;
  sep: string;
  named: boolean;
  ifemp: string;
  allowReserved: boolean;
}

function opInfoFor(op: string): OpInfo | null {
  switch (op) {
    case "": return { first: "", sep: ",", named: false, ifemp: "", allowReserved: false };
    case "+": return { first: "", sep: ",", named: false, ifemp: "", allowReserved: true };
    case "#": return { first: "#", sep: ",", named: false, ifemp: "", allowReserved: true };
    case ".": return { first: ".", sep: ".", named: false, ifemp: "", allowReserved: false };
    case "/": return { first: "/", sep: "/", named: false, ifemp: "", allowReserved: false };
    case ";": return { first: ";", sep: ";", named: true, ifemp: "", allowReserved: false };
    case "?": return { first: "?", sep: "&", named: true, ifemp: "=", allowReserved: false };
    case "&": return { first: "&", sep: "&", named: true, ifemp: "=", allowReserved: false };
    default: return null;
  }
}

// --- variable specs ------------------------------------------------------

interface VarSpec {
  name: string;
  explode: boolean;
  prefix: number;
  hasPrefix: boolean;
}

// --- value classification ------------------------------------------------

const enum Kind { Undef, Str, List, Assoc }

interface VarValue {
  kind: Kind;
  s?: string;
  list?: string[];
  pairs?: [string, string][];
}

function scalarToString(v: JsonValue): string | null {
  if (typeof v === "string") return v;
  if (typeof v === "number") return String(v);
  if (typeof v === "boolean") return v ? "true" : "false";
  return null;
}

function classify(v: JsonValue | undefined, present: boolean): VarValue {
  if (!present || v === null || v === undefined) return { kind: Kind.Undef };
  if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") {
    return { kind: Kind.Str, s: scalarToString(v)! };
  }
  if (Array.isArray(v)) {
    const items: string[] = [];
    for (const e of v) {
      const s = scalarToString(e);
      if (s !== null) items.push(s);
    }
    return { kind: Kind.List, list: items };
  }
  // plain object
  const pairs: [string, string][] = [];
  for (const k of Object.keys(v)) {
    const s = scalarToString((v as JsonObject)[k]);
    if (s !== null) pairs.push([k, s]);
  }
  return { kind: Kind.Assoc, pairs };
}

function isDefinedNonempty(v: VarValue): boolean {
  switch (v.kind) {
    case Kind.Undef: return false;
    case Kind.Str: return true;
    case Kind.List: return v.list!.length > 0;
    case Kind.Assoc: return v.pairs!.length > 0;
  }
}

// --- percent-encoding ----------------------------------------------------

function isUnreserved(b: number): boolean {
  return (
    (b >= 0x41 && b <= 0x5a) || // A-Z
    (b >= 0x61 && b <= 0x7a) || // a-z
    (b >= 0x30 && b <= 0x39) || // 0-9
    b === 0x2d || b === 0x2e || b === 0x5f || b === 0x7e // - . _ ~
  );
}

function isReserved(b: number): boolean {
  switch (b) {
    case 0x3a: case 0x2f: case 0x3f: case 0x23: case 0x5b: case 0x5d:
    case 0x40: case 0x21: case 0x24: case 0x26: case 0x27: case 0x28:
    case 0x29: case 0x2a: case 0x2b: case 0x2c: case 0x3b: case 0x3d:
      return true;
    default:
      return false;
  }
}

function isHex(b: number): boolean {
  return (b >= 0x30 && b <= 0x39) || (b >= 0x61 && b <= 0x66) || (b >= 0x41 && b <= 0x46);
}

// Percent-encode s. When allowReserved is set, reserved characters stay literal
// and existing %XX triplets are passed through untouched.
function pctEncode(s: string, allowReserved: boolean): string {
  const b = Buffer.from(s, "utf8");
  let out = "";
  let i = 0;
  while (i < b.length) {
    const c = b[i];
    if (c === 0x25 && allowReserved && i + 2 < b.length && isHex(b[i + 1]) && isHex(b[i + 2])) {
      out += "%" + String.fromCharCode(b[i + 1]) + String.fromCharCode(b[i + 2]);
      i += 3;
      continue;
    }
    if (isUnreserved(c) || (allowReserved && isReserved(c))) {
      out += String.fromCharCode(c);
    } else {
      out += "%" + c.toString(16).toUpperCase().padStart(2, "0");
    }
    i++;
  }
  return out;
}

function applyPrefixAndEncode(s: string, prefix: number, hasPrefix: boolean, allowReserved: boolean): string {
  let truncated = s;
  if (hasPrefix) {
    truncated = Array.from(s).slice(0, prefix).join("");
  }
  return pctEncode(truncated, allowReserved);
}

// --- template parsing ----------------------------------------------------

interface Part {
  isExpr: boolean;
  literal?: string;
  op?: string;
  specs?: VarSpec[];
}

function isControl(cp: number): boolean {
  return cp <= 0x1f || (cp >= 0x7f && cp <= 0x9f);
}

function validateLiteralChar(cp: number): boolean {
  if (isControl(cp)) return false;
  switch (cp) {
    case 0x20: case 0x22: case 0x3c: case 0x3e:
    case 0x5c: case 0x5e: case 0x60: case 0x7c:
      return false; // space " < > \ ^ ` |
    default:
      return true;
  }
}

function parseTemplate(t: string): Part[] | null {
  const chars = Array.from(t);
  const parts: Part[] = [];
  let i = 0;
  let lit = "";
  while (i < chars.length) {
    const c = chars[i];
    if (c === "{") {
      if (lit.length > 0) {
        parts.push({ isExpr: false, literal: lit });
        lit = "";
      }
      let j = i + 1;
      let body = "";
      let closed = false;
      while (j < chars.length) {
        if (chars[j] === "}") { closed = true; break; }
        if (chars[j] === "{") return null;
        body += chars[j];
        j++;
      }
      if (!closed) return null;
      const parsed = parseExpr(body);
      if (parsed === null) return null;
      parts.push({ isExpr: true, op: parsed.op, specs: parsed.specs });
      i = j + 1;
    } else if (c === "}") {
      return null;
    } else {
      if (!validateLiteralChar(c.codePointAt(0)!)) return null;
      lit += c;
      i++;
    }
  }
  if (lit.length > 0) parts.push({ isExpr: false, literal: lit });
  return parts;
}

function parseExpr(body: string): { op: string; specs: VarSpec[] } | null {
  if (body === "") return null;
  const bchars = Array.from(body);
  const first = bchars[0];
  let op: string;
  let restStart: number;
  if (first === "+" || first === "#" || first === "." || first === "/" ||
      first === ";" || first === "?" || first === "&") {
    op = first; restStart = 1;
  } else if (first === "=" || first === "," || first === "!" || first === "@" || first === "|") {
    return null;
  } else {
    op = ""; restStart = 0;
  }
  const rest = bchars.slice(restStart).join("");
  if (rest === "") return null;
  const specs: VarSpec[] = [];
  for (const p of rest.split(",")) {
    const vs = parseVarspec(p);
    if (vs === null) return null;
    specs.push(vs);
  }
  return { op, specs };
}

function allDigits(s: string): boolean {
  if (s.length === 0) return false;
  for (let i = 0; i < s.length; i++) {
    const c = s.charCodeAt(i);
    if (c < 0x30 || c > 0x39) return false;
  }
  return true;
}

function parseVarspec(s: string): VarSpec | null {
  if (s === "") return null;
  let explode = false;
  let hasPrefix = false;
  let prefix = 0;
  let name: string;
  const idx = s.indexOf(":");
  if (idx >= 0) {
    const n = s.slice(0, idx);
    const digits = s.slice(idx + 1);
    if (digits.length === 0 || digits.length > 4 || !allDigits(digits)) return null;
    prefix = parseInt(digits, 10);
    hasPrefix = true;
    name = n;
  } else if (s.endsWith("*")) {
    explode = true;
    name = s.slice(0, -1);
  } else {
    name = s;
  }
  if (!validateVarname(name)) return null;
  return { name, explode, prefix, hasPrefix };
}

function isAlnum(b: number): boolean {
  return (b >= 0x41 && b <= 0x5a) || (b >= 0x61 && b <= 0x7a) || (b >= 0x30 && b <= 0x39);
}

// varname = varchar *( ["."] varchar ), varchar = ALPHA / DIGIT / "_" /
// pct-encoded. Spaces, leading/trailing/doubled dots, and other punctuation
// are rejected.
function validateVarname(name: string): boolean {
  if (name === "") return false;
  if (name.startsWith(".") || name.endsWith(".") || name.includes("..")) return false;
  const b = Buffer.from(name, "utf8");
  let i = 0;
  while (i < b.length) {
    const c = b[i];
    if (c === 0x25) {
      if (i + 2 < b.length && isHex(b[i + 1]) && isHex(b[i + 2])) {
        i += 3;
        continue;
      }
      return false;
    }
    if (isAlnum(c) || c === 0x5f || c === 0x2e) {
      i++;
    } else {
      return false;
    }
  }
  return true;
}

// --- expansion -----------------------------------------------------------

function namedPair(name: string, encoded: string, isEmpty: boolean, info: OpInfo): string {
  if (isEmpty) return name + info.ifemp;
  return name + "=" + encoded;
}

function expandVarspec(info: OpInfo, spec: VarSpec, value: VarValue): string {
  switch (value.kind) {
    case Kind.Str: {
      const encoded = applyPrefixAndEncode(value.s!, spec.prefix, spec.hasPrefix, info.allowReserved);
      if (info.named) return namedPair(spec.name, encoded, value.s === "", info);
      return encoded;
    }
    case Kind.List: {
      if (spec.explode) {
        const parts: string[] = [];
        for (const it of value.list!) {
          const enc = pctEncode(it, info.allowReserved);
          if (info.named) parts.push(namedPair(spec.name, enc, it === "", info));
          else parts.push(enc);
        }
        return parts.join(info.sep);
      }
      const joined = value.list!.map((it) => pctEncode(it, info.allowReserved));
      const body = joined.join(",");
      if (info.named) return spec.name + "=" + body;
      return body;
    }
    case Kind.Assoc: {
      if (spec.explode) {
        const parts: string[] = [];
        for (const [k, v] of value.pairs!) {
          const ek = pctEncode(k, info.allowReserved);
          const ev = pctEncode(v, info.allowReserved);
          if (info.named && v === "") parts.push(ek + info.ifemp);
          else parts.push(ek + "=" + ev);
        }
        return parts.join(info.sep);
      }
      const flat: string[] = [];
      for (const [k, v] of value.pairs!) {
        flat.push(pctEncode(k, info.allowReserved));
        flat.push(pctEncode(v, info.allowReserved));
      }
      const body = flat.join(",");
      if (info.named) return spec.name + "=" + body;
      return body;
    }
    default:
      return "";
  }
}

function expandExpr(op: string, specs: VarSpec[], vars: JsonObject): string | null {
  const info = opInfoFor(op)!;
  const pieces: string[] = [];
  for (const spec of specs) {
    const present = Object.prototype.hasOwnProperty.call(vars, spec.name);
    const value = classify(present ? vars[spec.name] : undefined, present);
    // A prefix (:N) modifier is valid only on string values; applying it to a
    // list or associative value is a malformed template.
    if (spec.hasPrefix && (value.kind === Kind.List || value.kind === Kind.Assoc)) {
      return null;
    }
    if (!isDefinedNonempty(value)) continue;
    pieces.push(expandVarspec(info, spec, value));
  }
  if (pieces.length === 0) return "";
  return info.first + pieces.join(info.sep);
}

function expand(parts: Part[], vars: JsonObject): string | null {
  let out = "";
  for (const p of parts) {
    if (p.isExpr) {
      const s = expandExpr(p.op!, p.specs!, vars);
      if (s === null) return null;
      out += s;
    } else {
      out += p.literal;
    }
  }
  return out;
}

// --- input plumbing ------------------------------------------------------

function parseInput(input: string): { template: string; vars: JsonObject } | null {
  let root: JsonValue;
  try {
    root = JSON.parse(input);
  } catch {
    return null;
  }
  if (typeof root !== "object" || root === null || Array.isArray(root)) return null;
  const obj = root as JsonObject;
  const tv = obj["template"];
  if (typeof tv !== "string") return null;
  let vars: JsonObject;
  if (!Object.prototype.hasOwnProperty.call(obj, "variables")) {
    vars = {};
  } else {
    const vv = obj["variables"];
    if (typeof vv === "object" && vv !== null && !Array.isArray(vv)) {
      vars = vv as JsonObject;
    } else {
      return null;
    }
  }
  return { template: tv, vars };
}

function runTool(input: string): string | null {
  const parsed = parseInput(input);
  if (parsed === null) return null;
  const parts = parseTemplate(parsed.template);
  if (parts === null) return null;
  return expand(parts, parsed.vars);
}

function main(): void {
  let input: string;
  try {
    input = fs.readFileSync(0, "utf8");
  } catch {
    process.stdout.write("ERROR\n");
    process.exit(1);
  }
  const result = runTool(input);
  if (result === null) {
    process.stdout.write("ERROR\n");
    process.exit(1);
  }
  process.stdout.write(result + "\n");
}

main();
