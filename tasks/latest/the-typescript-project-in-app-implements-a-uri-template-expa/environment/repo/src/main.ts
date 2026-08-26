// URI Template expansion tool.
//
// Reads a JSON object {"template": <string>, "variables": <object>} from stdin
// and writes the expanded URI to stdout. Malformed templates should be
// reported by writing "ERROR" and exiting with a non-zero status.
//
// The expansion routine below is a placeholder that does not yet interpret any
// expression syntax.

import * as fs from "fs";

type JsonValue = string | number | boolean | null | JsonValue[] | JsonObject;
interface JsonObject {
  [k: string]: JsonValue;
}

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

// expandTemplate expands a URI template against a set of variables.
//
// TODO: implement the expansion algorithm. For now this returns the template
// text unchanged.
function expandTemplate(template: string, _vars: JsonObject): string | null {
  return template;
}

function runTool(input: string): string | null {
  const parsed = parseInput(input);
  if (parsed === null) return null;
  return expandTemplate(parsed.template, parsed.vars);
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
