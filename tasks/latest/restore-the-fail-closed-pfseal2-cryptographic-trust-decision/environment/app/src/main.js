import process from 'node:process';
import { parseArgs, USAGE } from './cli.js';
import { UsageError } from './errors.js';
import { runWorker } from './worker.js';

export async function main(argv) {
  try {
    const options = parseArgs(argv);
    if (options.help) {
      process.stdout.write(`${USAGE}\n`);
      return;
    }
    const summary = await runWorker(options);
    process.stdout.write(`${JSON.stringify(summary)}\n`);
  } catch (error) {
    const message = error instanceof UsageError ? error.message : 'fatal worker error';
    process.stderr.write(`pfseal-worker: ${message}\n`);
    process.exitCode = error instanceof UsageError ? 64 : 70;
  }
}
