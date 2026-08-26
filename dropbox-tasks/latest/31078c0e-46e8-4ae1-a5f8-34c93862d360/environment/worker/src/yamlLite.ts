type Frame = { indent: number; container: any; key?: string };

function scalar(text: string): any {
  const value = text.trim();
  if (value === "") return "";
  if (value === "null" || value === "~") return null;
  if (value === "true") return true;
  if (value === "false") return false;
  if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
    return value.slice(1, -1);
  }
  if (/^-?\d+(\.\d+)?([eE][+-]?\d+)?$/.test(value)) return Number(value);
  return value;
}

function splitKeyValue(text: string): [string, string] {
  const idx = text.indexOf(":");
  if (idx < 0) throw new Error(`YAML line is missing ':'`);
  return [text.slice(0, idx).trim(), text.slice(idx + 1).trim()];
}

function stripComment(line: string): string {
  let quote: string | null = null;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if ((ch === '"' || ch === "'") && line[i - 1] !== "\\") {
      quote = quote === ch ? null : quote ?? ch;
    }
    if (ch === "#" && quote === null) return line.slice(0, i);
  }
  return line;
}

export function parseYamlLite(text: string): any {
  const root: any = {};
  const stack: Frame[] = [{ indent: -1, container: root }];
  const rawLines = text.replace(/\r\n/g, "\n").split("\n");

  for (const rawLine of rawLines) {
    const withoutComment = stripComment(rawLine).replace(/\s+$/, "");
    if (!withoutComment.trim()) continue;
    const indent = withoutComment.length - withoutComment.trimStart().length;
    const content = withoutComment.trimStart();

    while (stack.length > 1 && indent <= stack[stack.length - 1].indent) stack.pop();
    const parent = stack[stack.length - 1].container;

    if (content.startsWith("- ")) {
      if (!Array.isArray(parent)) throw new Error("YAML list item without list parent");
      const rest = content.slice(2).trim();
      if (!rest) {
        const obj: any = {};
        parent.push(obj);
        stack.push({ indent, container: obj });
        continue;
      }
      if (rest.includes(":")) {
        const [key, value] = splitKeyValue(rest);
        const obj: any = {};
        obj[key] = value === "" ? {} : scalar(value);
        parent.push(obj);
        if (value === "") stack.push({ indent, container: obj[key] });
        else stack.push({ indent, container: obj });
      } else {
        parent.push(scalar(rest));
      }
      continue;
    }

    const [key, value] = splitKeyValue(content);
    if (value === "") {
      const nextContainer: any = key === "dimensions" ? [] : {};
      parent[key] = nextContainer;
      stack.push({ indent, container: nextContainer, key });
    } else {
      parent[key] = scalar(value);
    }
  }
  return root;
}
