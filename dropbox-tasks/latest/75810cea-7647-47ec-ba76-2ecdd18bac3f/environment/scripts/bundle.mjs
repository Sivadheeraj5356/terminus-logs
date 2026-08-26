import { readJson, writeJson } from '../tools/json.mjs';

const root = process.cwd();
const graph = readJson(`${root}/generated/plan-graph.json`);
const providers = {
  consoleRuntime: graph.importers['apps/console']['@harbor/runtime']
    .replace('workspace:', '')
    .split('@*')[0],
  consoleAdapter: graph.importers['apps/console']['@harbor/adapter']
    .replace('workspace:', '')
    .split('@*')[0],
  workerRuntime: graph.importers['apps/worker']['@harbor/runtime']
    .replace('workspace:', '')
    .split('@*')[0],
  workerPlugin: graph.importers['apps/worker']['@harbor/plugin']
    .replace('workspace:', '')
    .split('@*')[0],
};
writeJson(`${root}/reports/build-summary.json`, {
  schema: 'migrate-build-summary-v1',
  train: graph.train,
  epoch: graph.epoch,
  providers,
  peers: graph.peers,
  fingerprint: graph.fingerprint,
});
console.log(JSON.stringify({ built: true, providers }));
