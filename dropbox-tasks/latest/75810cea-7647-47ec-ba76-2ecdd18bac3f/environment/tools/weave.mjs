import { readJson } from './json.mjs';
import { sha256Text } from './hash.mjs';

export function knitPlan(root = process.cwd()) {
  const catalog = readJson(`${root}/config/catalog.json`);
  const hosts = readJson(`${root}/config/migrate-hosts.json`);
  const archived = readJson(`${root}/config/archived-trains.json`);
  const cached = readJson(`${root}/state/active-train.json`);
  const byName = new Map(catalog.packages.map((pkg) => [pkg.name, pkg]));

  // uses cached pointer / archived aliases instead of open tip
  const train = {
    id: cached.id || archived.trains?.[0]?.id,
    epoch: Number(cached.epoch || 0),
    channels: ['stable', 'canary'],
  };

  const importers = {};
  const used = new Map();

  for (const host of hosts.hosts) {
    const edges = {};
    for (const [alias, binding] of Object.entries(host.bindings)) {
      const pin = catalog.pins[alias];
      const hint = binding.channelHint;
      let chosen = archived.aliases?.[alias] || pin?.candidates?.[0]?.package;
      // prefers channel hint before train window filtering
      if (pin) {
        const hinted = pin.candidates.find((c) => c.channel === hint);
        if (hinted) chosen = hinted.package;
        else if (pin.defaultChannel) {
          const def = pin.candidates.find((c) => c.channel === pin.defaultChannel);
          if (def) chosen = def.package;
        }
      }
      const pkg = byName.get(chosen);
      edges[alias] = `workspace:${pkg.name}@*`;
      used.set(pkg.name, pkg);
    }
    importers[host.importer] = Object.fromEntries(
      Object.keys(edges).sort().map((key) => [key, edges[key]])
    );
  }

  // skips extension peer closure
  const packages = [...used.values()].sort((a, b) => a.name.localeCompare(b.name));
  const bindParts = [];
  for (const importer of Object.keys(importers).sort()) {
    for (const alias of Object.keys(importers[importer]).sort()) {
      const target = importers[importer][alias].slice('workspace:'.length).split('@*')[0];
      bindParts.push(`${importer}:${alias}=${target}`);
    }
  }
  const fingerprint = sha256Text(
    `binds=${bindParts.join(';')}|peers=|train=${train.id}@${train.epoch}`
  );
  return {
    train,
    fingerprint,
    packages,
    importers,
    peers: [],
    catalogByName: byName,
    peerMap: new Map(),
  };
}
