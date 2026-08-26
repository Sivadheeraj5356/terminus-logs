import * as fs from "fs/promises";
import * as path from "path";
import { ValidationReport, CoveredException } from "./types";
import { parseLsofOutput, filterPersistentFds } from "./parsers/lsof";

export interface ValidateOptions {
  outputDir: string;
  contractsPath: string;
  dossierPath: string;
  lsofPath: string;
}

// TODO: implement validateMigration
// Must check all fields defined in migration-requirements.md including:
//   - limit_nofile_valid: LimitNOFILE > contracts.fd_count_observed
//   - start_limit_policy_valid: StartLimitBurst=5 AND StartLimitIntervalSec=10min present
export async function validateMigration(opts: ValidateOptions): Promise<ValidationReport> {
  throw new Error("not implemented");
}
