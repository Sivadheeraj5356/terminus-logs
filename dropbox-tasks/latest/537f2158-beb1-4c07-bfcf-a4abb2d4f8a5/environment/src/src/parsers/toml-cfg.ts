import * as fs from "fs/promises";
import toml from "@iarna/toml";

export async function loadToml<T>(filePath: string): Promise<T> {
  const text = await fs.readFile(filePath, "utf8");
  return toml.parse(text) as unknown as T;
}
