'use strict';

const Fastify = require('fastify');
const { getRedis } = require('./redis-client');
const { loadConfig } = require('./config');

const FIELDS = ['borough', 'zone', 'service_zone'];

function shape(id, h) {
  return {
    location_id: id,
    borough: h.borough,
    zone: h.zone,
    service_zone: h.service_zone,
    version: Number.parseInt(h.version || '0', 10),
  };
}

function build() {
  const app = Fastify({ logger: false });
  const redis = getRedis();

  app.get('/health', async () => {
    return { status: 'ok' };
  });

  app.get('/zones', async () => {
    const keys = await redis.keys('zone:*');
    const zones = [];
    for (const key of keys) {
      const h = await redis.hgetall(key);
      if (!h || Object.keys(h).length === 0) continue;
      const id = Number.parseInt(key.slice('zone:'.length), 10);
      zones.push(shape(id, h));
    }
    zones.sort((a, b) => a.location_id - b.location_id);
    return zones;
  });

  app.get('/zones/:id', async (request, reply) => {
    const id = Number.parseInt(request.params.id, 10);
    const h = await redis.hgetall(`zone:${id}`);
    if (!h || Object.keys(h).length === 0) {
      reply.code(404);
      return { error: 'not found' };
    }
    return shape(id, h);
  });

  app.put('/zones/:id', async (request, reply) => {
    const id = Number.parseInt(request.params.id, 10);
    const key = `zone:${id}`;
    const h = await redis.hgetall(key);
    if (!h || Object.keys(h).length === 0) {
      reply.code(404);
      return { error: 'not found' };
    }

    const body = request.body || {};
    const update = {};
    let changed = false;
    for (const f of FIELDS) {
      if (body[f] !== undefined && body[f] !== h[f]) {
        update[f] = body[f];
        changed = true;
      }
    }

    if (changed) {
      update.version = String(Number.parseInt(h.version || '0', 10) + 1);
      await redis.hset(key, update);
    }

    const fresh = await redis.hgetall(key);
    return shape(id, fresh);
  });

  return app;
}

async function start() {
  const cfg = loadConfig();
  const app = build();
  await app.listen({ host: '0.0.0.0', port: cfg.http.port });
}

if (require.main === module) {
  start().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}

module.exports = { build, FIELDS };
