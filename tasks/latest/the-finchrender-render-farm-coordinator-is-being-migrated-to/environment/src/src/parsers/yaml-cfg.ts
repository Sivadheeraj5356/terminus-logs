import * as fs from "fs/promises";
import * as yaml from "js-yaml";

export async function loadYaml<T>(filePath: string): Promise<T> {
  const text = await fs.readFile(filePath, "utf8");
  return yaml.load(text) as T;
}
