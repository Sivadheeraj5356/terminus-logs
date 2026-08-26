#!/usr/bin/env node
// cli.js
// flaky-repro CLI — internal QA tool for Playwright flaky-test investigation.
// Usage:
//   node cli.js report             # Generate historical flaky summary
//   node cli.js plan [--session]   # Generate Playwright reproduction plan
//   node cli.js run [--session]    # Execute plan and write execution report

const { program } = require('commander');
const fs = require('fs');
const path = require('path');

const { generateReport } = require('./lib/history');
const { getPrioritizedFlaky } = require('./lib/history');
const { generatePlan } = require('./lib/planner');
const { runAndReport } = require('./lib/executor');

const LOGS_DIR = path.join(__dirname, 'logs');

function ensureLogs() {
  if (!fs.existsSync(LOGS_DIR)) {
    fs.mkdirSync(LOGS_DIR, { recursive: true });
  }
}

program
  .name('flaky-repro')
  .description('Internal QA tooling for Playwright flaky-test investigation')
  .version('2.1.4');

program
  .command('report')
  .description('Generate historical flaky-test prioritization report')
  .action(async () => {
    try {
      ensureLogs();
      const report = await generateReport();
      const outPath = path.join(LOGS_DIR, 'report.json');
      fs.writeFileSync(outPath, JSON.stringify(report, null, 2));
      console.log(`Report written to ${outPath}`);
      console.log(`Flaky combos: ${report.total_flaky_combos}`);
    } catch (err) {
      console.error('report failed:', err.message);
      process.exit(1);
    }
  });

program
  .command('plan')
  .description('Generate Playwright reproduction plan for top flaky specs')
  .option('--session <id>', 'Session identifier for this plan', 'plan-sess-alpha')
  .option('--limit <n>', 'Max flaky entries to include', '20')
  .action(async (opts) => {
    try {
      ensureLogs();
      const limit = parseInt(opts.limit, 10);
      const flaky = await getPrioritizedFlaky(limit);
      const plan = await generatePlan(flaky, opts.session);
      const outPath = path.join(LOGS_DIR, 'plan.json');
      fs.writeFileSync(outPath, JSON.stringify(plan, null, 2));
      console.log(`Plan written to ${outPath}`);
      console.log(`Projects: ${plan.projects.length}, specs: ${plan.total_specs}`);
    } catch (err) {
      console.error('plan failed:', err.message);
      process.exit(1);
    }
  });

program
  .command('run')
  .description('Execute reproduction plan and write execution report')
  .option('--session <id>', 'Session identifier matching the plan', 'plan-sess-alpha')
  .action(async (opts) => {
    try {
      ensureLogs();
      const planPath = path.join(LOGS_DIR, 'plan.json');
      if (!fs.existsSync(planPath)) {
        console.error('No plan.json found. Run `flaky-repro plan` first.');
        process.exit(1);
      }
      const plan = JSON.parse(fs.readFileSync(planPath, 'utf8'));
      plan.session_id = opts.session;
      const report = await runAndReport(plan);
      console.log(`Execution report written to ${LOGS_DIR}/execution_report.json`);
      console.log(`Passed: ${report.passed_count}, Failed: ${report.failed_count}, Flaky: ${report.flaky_count}`);
    } catch (err) {
      console.error('run failed:', err.message);
      process.exit(1);
    }
  });

program.parse();
