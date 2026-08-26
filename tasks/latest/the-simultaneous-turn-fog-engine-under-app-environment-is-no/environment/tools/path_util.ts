import * as path from "path";

export function underApp(...parts: string[]): string {
  return path.posix.join("/app", ...parts);
}
