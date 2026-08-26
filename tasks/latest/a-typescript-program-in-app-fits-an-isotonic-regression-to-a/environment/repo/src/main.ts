/*
 * Standard-input / standard-output framing for isotonic regression.
 *
 * Reads one JSON object {"inputs": [ <input>, ... ]} from standard input and
 * writes one JSON object {"results": [ {"pred": [...]}, ... ]} to standard
 * output, one result per input in the same order. This wiring is complete; the
 * work is in isotonic.ts.
 */

import * as fs from "node:fs";
import { fitPredict } from "./isotonic.ts";
import type { IsotonicInput } from "./isotonic.ts";

type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | { [key: string]: JsonValue };

class Json {
  private s: string;
  private i: number;

  constructor(s: string) {
    this.s = s;
    this.i = 0;
  }

  private ws(): void {
    while (this.i < this.s.length && /\s/.test(this.s[this.i])) this.i++;
  }

  value(): JsonValue {
    this.ws();
    switch (this.s[this.i]) {
      case "{":
        return this.obj();
      case "[":
        return this.arr();
      case '"':
        return this.str();
      case "t":
        this.i += 4;
        return true;
      case "f":
        this.i += 5;
        return false;
      case "n":
        this.i += 4;
        return null;
      default:
        return this.num();
    }
  }

  private obj(): { [key: string]: JsonValue } {
    const m: { [key: string]: JsonValue } = {};
    this.i++;
    this.ws();
    if (this.s[this.i] === "}") {
      this.i++;
      return m;
    }
    while (true) {
      this.ws();
      const k = this.str();
      this.ws();
      this.i++;
      m[k] = this.value();
      this.ws();
      if (this.s[this.i] === ",") {
        this.i++;
        continue;
      }
      if (this.s[this.i] === "}") {
        this.i++;
        break;
      }
    }
    return m;
  }

  private arr(): JsonValue[] {
    const a: JsonValue[] = [];
    this.i++;
    this.ws();
    if (this.s[this.i] === "]") {
      this.i++;
      return a;
    }
    while (true) {
      a.push(this.value());
      this.ws();
      if (this.s[this.i] === ",") {
        this.i++;
        continue;
      }
      if (this.s[this.i] === "]") {
        this.i++;
        break;
      }
    }
    return a;
  }

  private str(): string {
    let sb = "";
    this.i++;
    while (this.s[this.i] !== '"') {
      if (this.s[this.i] === "\\") {
        this.i++;
        switch (this.s[this.i]) {
          case "n":
            sb += "\n";
            break;
          case "t":
            sb += "\t";
            break;
          case "r":
            sb += "\r";
            break;
          case '"':
            sb += '"';
            break;
          case "\\":
            sb += "\\";
            break;
          case "/":
            sb += "/";
            break;
          default:
            sb += this.s[this.i];
        }
      } else {
        sb += this.s[this.i];
      }
      this.i++;
    }
    this.i++;
    return sb;
  }

  private num(): number {
    const start = this.i;
    if (this.s[this.i] === "-" || this.s[this.i] === "+") this.i++;
    while (this.i < this.s.length) {
      const c = this.s[this.i];
      if (
        (c >= "0" && c <= "9") ||
        c === "." ||
        c === "e" ||
        c === "E" ||
        c === "+" ||
        c === "-"
      ) {
        this.i++;
      } else {
        break;
      }
    }
    return Number(this.s.substring(start, this.i));
  }
}

function asNum(v: JsonValue): number {
  return v as number;
}

function toInput(m: { [key: string]: JsonValue }): IsotonicInput {
  const x = (m["x"] as JsonValue[]).map(asNum);
  const y = (m["y"] as JsonValue[]).map(asNum);
  const weightRaw = m["weight"];
  const weight =
    weightRaw === null ? null : (weightRaw as JsonValue[]).map(asNum);
  const increasing = m["increasing"] as boolean;
  const queries = (m["queries"] as JsonValue[]).map(asNum);
  return { x, y, weight, increasing, queries };
}

function fmt(v: number): string {
  if (Number.isNaN(v)) return "0";
  // full-precision, round-trippable output
  return String(v);
}

function main(): void {
  const input = fs.readFileSync(0, "utf-8");
  const root = new Json(input).value() as { [key: string]: JsonValue };
  const inputs = (root["inputs"] as JsonValue[]).map((it) =>
    toInput(it as { [key: string]: JsonValue }),
  );
  let sb = "";
  sb += '{"results":[';
  inputs.forEach((inp, idx) => {
    if (idx > 0) sb += ",";
    const pred = fitPredict(inp);
    sb += '{"pred":[';
    pred.forEach((v, j) => {
      if (j > 0) sb += ",";
      sb += fmt(v);
    });
    sb += "]}";
  });
  sb += "]}";
  process.stdout.write(sb + "\n");
}

main();
