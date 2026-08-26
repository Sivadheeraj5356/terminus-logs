'use strict';

// Developer convenience: load the Redis keyspace from the committed seed file so
// you can exercise the service locally. The verifier seeds Redis independently.
const fs = require('fs');
const { getRedis, closeRedis } = require('../src/redis-client');

const SEED_PATH = process.env.SEED_PATH || '/app/data/zones.seed.json';

async function main() {
  const redis = getRedis();
  const seed = JSON.parse(fs.readFileSync(SEED_PATH, 'utf8'));

  const existing = await redis.keys('zone:*');
  if (existing.length) await redis.del(...existing);

  for (const z of seed.zones) {
    await redis.hset(`zone:${z.location_id}`, {
      borough: z.borough,
      zone: z.zone,
      service_zone: z.service_zone,
      version: String(z.version),
    });
  }
  process.stdout.write(`seeded ${seed.zones.length} zones\n`);
  await closeRedis();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
