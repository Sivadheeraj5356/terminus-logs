import Redis from "ioredis";

const USERS_KEY = "bastion:users";
const SSH_KEYS_KEY = "bastion:ssh_keys:archive";
const SERVICE_KEY = "bastion:service_accounts";
const MODES_KEY = "bastion:file_modes";
const SSHD_KEY = "bastion:sshd_settings";
const SUDOERS_KEY = "bastion:sudoers_lines";
const REGISTRY_CACHE_PREFIX = "bastion:registry:cache:";

function tenantOverlayKey(tenant) {
  return `bastion:tenant:overrides:${tenant}`;
}

function parseHash(raw) {
  const out = {};
  for (const [field, value] of Object.entries(raw)) {
    try {
      out[field] = JSON.parse(value);
    } catch {
      out[field] = value;
    }
  }
  return out;
}

async function hgetall(redis, key) {
  const raw = await redis.hgetall(key);
  return raw ?? {};
}

export function createRedisClient() {
  const url = process.env.REDIS_URL ?? "redis://127.0.0.1:6379";
  return new Redis(url);
}

export async function loadRegistry(redis, tenant = "prod") {
  const users = parseHash(await hgetall(redis, USERS_KEY));
  const sshKeys = await hgetall(redis, SSH_KEYS_KEY);
  const fileModes = await hgetall(redis, MODES_KEY);
  const sshdSettings = parseHash(await hgetall(redis, SSHD_KEY));
  const sudoersLines = await hgetall(redis, SUDOERS_KEY);
  const serviceAccounts = await redis.smembers(SERVICE_KEY);

  const cache = await hgetall(redis, `${REGISTRY_CACHE_PREFIX}${tenant}`);
  const overlay = await hgetall(redis, tenantOverlayKey(tenant));
  const effectiveOverlay =
    Object.keys(cache).length > 0 ? { ...overlay, ...cache } : overlay;
  const mergedModes = { ...fileModes, ...effectiveOverlay };
  const mergedSshd = { ...sshdSettings };
  if (effectiveOverlay.sshd_settings) {
    mergedSshd.sshd_settings = effectiveOverlay.sshd_settings;
  }

  return {
    tenant,
    users,
    sshKeys,
    fileModes: mergedModes,
    sshdSettings: mergedSshd,
    sudoersLines,
    serviceAccounts,
  };
}
