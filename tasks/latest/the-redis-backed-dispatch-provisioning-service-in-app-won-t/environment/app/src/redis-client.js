'use strict';

const Redis = require('ioredis');
const { loadConfig } = require('./config');

let client = null;

function getRedis() {
  if (client) return client;
  const cfg = loadConfig();
  client = new Redis(cfg.redis.url);
  return client;
}

async function closeRedis() {
  if (client) {
    await client.quit();
    client = null;
  }
}

module.exports = { getRedis, closeRedis };
