import { DuckDBInstance } from '@duckdb/node-api';

export async function runWorker(options) {
  const instance = await DuckDBInstance.create(options.db);
  instance.closeSync();
  throw new Error('PFSEAL2 worker is not implemented');
}
