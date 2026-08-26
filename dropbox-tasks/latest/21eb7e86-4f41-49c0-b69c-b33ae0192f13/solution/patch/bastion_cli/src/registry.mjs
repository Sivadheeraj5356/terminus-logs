import Redis from "ioredis";

const USERS_KEY = "bastion:users";
const SSH_KEYS_KEY = "bastion:ssh_keys";
const SERVICE_KEY = "bastion:service_accounts";
const MODES_KEY = "bastion:file_modes";
const SSHD_KEY = "bastion:sshd_settings";
const SUDOERS_KEY = "bastion:sudoers_lines";

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

function mergeSshdSettings(globalMap, overlayJson) {
  const merged = { ...globalMap };
  const overlay = JSON.parse(overlayJson);
  for (const [path, directives] of Object.entries(overlay)) {
    merged[path] = { ...(merged[path] ?? {}), ...directives };
  }
  return merged;
}

export async function loadRegistry(redis, tenant = "prod") {
  const users = parseHash(await hgetall(redis, USERS_KEY));
  const sshKeys = await hgetall(redis, SSH_KEYS_KEY);
  const fileModes = await hgetall(redis, MODES_KEY);
  let sshdSettings = parseHash(await hgetall(redis, SSHD_KEY));
  const sudoersLines = await hgetall(redis, SUDOERS_KEY);
  const serviceAccounts = await redis.smembers(SERVICE_KEY);

  const overlay = await hgetall(redis, `bastion:overrides:tenant:${tenant}`);
  if (overlay.sshd_settings) {
    sshdSettings = mergeSshdSettings(sshdSettings, overlay.sshd_settings);
  }

  return {
    tenant,
    users,
    sshKeys,
    fileModes,
    sshdSettings,
    sudoersLines,
    serviceAccounts,
  };
}
