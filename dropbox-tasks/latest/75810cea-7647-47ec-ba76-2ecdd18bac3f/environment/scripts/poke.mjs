import { existsSync } from 'node:fs';
const root = process.cwd();
const required = [
  'config/catalog.json',
  'config/release-trains.json',
  'config/migrate-hosts.json',
  'config/extensions.json',
  'tools/weave.mjs',
  'tools/cask.mjs',
];
for (const rel of required) {
  if (!existsSync(`${root}/${rel}`)) {
    console.error(`missing ${rel}`);
    process.exit(1);
  }
}
console.log(JSON.stringify({ smoke: 'ok' }));
