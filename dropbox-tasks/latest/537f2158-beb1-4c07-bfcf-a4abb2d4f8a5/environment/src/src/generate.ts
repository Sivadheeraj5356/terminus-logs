import { RuntimeContracts } from "./types";

export interface GenerateOptions {
  contracts: RuntimeContracts;
  outputDir: string;
}

export async function generateSystemdConfig(opts: GenerateOptions): Promise<void> {
  throw new Error("Not implemented");
}
