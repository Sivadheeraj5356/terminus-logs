import * as fs from "fs/promises";
import * as path from "path";
import { Command } from "commander";
import { extractContracts } from "./extract";
import { generateSystemdConfig } from "./generate";
import { validateMigration } from "./validate";
import { auditSyscalls } from "./audit";

const STRACE_PATH = "/app/traces/startup-cold.strace";
const TRACES_DIR = "/app/traces";
const LSOF_STEADY_PATH = "/app/traces/steady-state.lsof";
const LSOF_LOAD_PATH = "/app/traces/under-load.lsof";
const YAML_PATH = "/app/legacy/coordinator.yaml";
const TOML_PATH = "/app/legacy/system.toml";
const DOSSIER_PATH = "/app/docs/ops-dossier.md";
const OUTPUT_DIR = "/app/output";
const CONTRACTS_PATH = path.join(OUTPUT_DIR, "contracts.json");
const REPORT_PATH = path.join(OUTPUT_DIR, "validation-report.json");
const AUDIT_PATH = path.join(OUTPUT_DIR, "syscall-audit.json");

const program = new Command();
program.name("finchrender-migrate").description("FinchRender systemd migration tooling");

program
  .command("extract")
  .description("Extract runtime contracts from traces and configs")
  .action(async () => {
    await fs.mkdir(OUTPUT_DIR, { recursive: true });
    const contracts = await extractContracts({
      stracePath: STRACE_PATH,
      tracesDir: TRACES_DIR,
      lsofPath: LSOF_STEADY_PATH,
      yamlPath: YAML_PATH,
      tomlPath: TOML_PATH,
      dossierPath: DOSSIER_PATH,
    });
    await fs.writeFile(CONTRACTS_PATH, JSON.stringify(contracts, null, 2));
    console.log(`Contracts written to ${CONTRACTS_PATH}`);
  });

program
  .command("generate")
  .description("Generate systemd unit files from contracts.json")
  .action(async () => {
    await fs.mkdir(OUTPUT_DIR, { recursive: true });
    const raw = await fs.readFile(CONTRACTS_PATH, "utf8");
    const contracts = JSON.parse(raw);
    await generateSystemdConfig({ contracts, outputDir: OUTPUT_DIR });
    console.log(`Systemd config written to ${OUTPUT_DIR}`);
  });

program
  .command("validate")
  .description("Validate generated systemd config against dossier and contracts")
  .action(async () => {
    await fs.mkdir(OUTPUT_DIR, { recursive: true });
    const report = await validateMigration({
      outputDir: OUTPUT_DIR,
      contractsPath: CONTRACTS_PATH,
      dossierPath: DOSSIER_PATH,
      lsofPath: LSOF_LOAD_PATH,
    });
    await fs.writeFile(REPORT_PATH, JSON.stringify(report, null, 2));
    console.log(`Validation report written to ${REPORT_PATH}`);
    if (!report.passed) {
      console.error("Validation FAILED. Issues:");
      report.issues.forEach((i) => console.error(" -", i));
      process.exit(1);
    }
  });

program
  .command("audit")
  .description("Audit syscalls across all strace captures and emit hardening files")
  .action(async () => {
    await fs.mkdir(OUTPUT_DIR, { recursive: true });
    const contractsRaw = await fs.readFile(CONTRACTS_PATH, "utf8");
    const contracts = JSON.parse(contractsRaw);
    await auditSyscalls({
      tracesDir: TRACES_DIR,
      outputDir: OUTPUT_DIR,
      contracts,
    });
    console.log(`Syscall audit written to ${AUDIT_PATH}`);
  });

program.parse(process.argv);
