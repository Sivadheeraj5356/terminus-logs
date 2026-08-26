import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const appDir = process.env.APP_DIR || "/app";
const testDir = process.env.TEST_DIR || "/tests";
const hashesPath = process.env.TASK_EXPECTED_HASHES_PATH || path.join(testDir, "expected_hashes.json");

function takeVerifierKey() {
  const keyPath = process.env.TASK_VERIFIER_HMAC_KEY_FILE || "";
  delete process.env.TASK_VERIFIER_HMAC_KEY_FILE;
  delete process.env.TASK_EXPECTED_HASHES_PATH;
  if (!keyPath) throw new Error("missing verifier key file");
  const key = fs.readFileSync(keyPath, "utf8").trim();
  try { fs.unlinkSync(keyPath); } catch {}
  if (!key) throw new Error("empty verifier key");
  return key;
}

const verifierKey = takeVerifierKey();
const setupNonces = new Set();
let acceptedRunBinding = null;

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object") {
    const ordered = {};
    for (const key of Object.keys(value).sort()) {
      if (key !== "result_proof") ordered[key] = canonical(value[key]);
    }
    return ordered;
  }
  return value;
}

function hmac(value) {
  return crypto.createHmac("sha256", verifierKey).update(JSON.stringify(canonical(value))).digest("hex");
}

function header(request, name) {
  const value = request.headers[name.toLowerCase()];
  return Array.isArray(value) ? String(value[0] || "") : String(value || "");
}

function equalHex(left, right) {
  if (!/^[a-f0-9]{64}$/i.test(left) || !/^[a-f0-9]{64}$/i.test(right)) return false;
  return crypto.timingSafeEqual(Buffer.from(left, "hex"), Buffer.from(right, "hex"));
}

function normalizedHash(filePath) {
  const text = fs.readFileSync(filePath, "utf8").replace(/\r\n/g, "\n").replace(/\r/g, "\n").replace(/\n*$/, "\n");
  return crypto.createHash("sha256").update(text).digest("hex");
}

function verifyProtectedFiles() {
  const expected = JSON.parse(fs.readFileSync(hashesPath, "utf8"));
  for (const [relativePath, expectedHash] of Object.entries(expected)) {
    const observed = normalizedHash(path.join(appDir, relativePath));
    if (observed !== expectedHash) throw new Error(`protected file hash mismatch: ${relativePath}`);
  }
}

function proofCore(payload) {
  return {
    status: payload.status,
    end_reason: payload.end_reason,
    turn: payload.turn,
    score: payload.score,
    scenario_id: payload.scenario?.id,
    objective_reached: payload.summary?.objective_reached,
    completed_turn: payload.summary?.completed_turn,
    reports_filed: payload.summary?.reports_filed
  };
}

function authorizeNewGame({ request, body }) {
  const nonce = header(request, "x-setup-nonce");
  const signature = header(request, "x-setup-hmac");
  if (!nonce || setupNonces.has(nonce)) return false;
  const expected = hmac({ method: "POST", path: "/new_game", nonce, payload: body });
  if (!equalHex(signature, expected)) return false;
  setupNonces.add(nonce);
  acceptedRunBinding = hmac({ scenario_id: body.scenario_id, seed: body.seed });
  return true;
}

function finalizeState(payload, request) {
  const nonce = header(request, "x-state-nonce");
  verifyProtectedFiles();
  if (!nonce) return payload;
  if (!acceptedRunBinding) throw new Error("accepted run binding is missing");
  return {
    ...payload,
    result_proof: {
      algorithm: "hmac-sha256",
      method: "GET",
      path: "/state",
      nonce_hash: crypto.createHash("sha256").update(nonce).digest("hex"),
      run_binding: acceptedRunBinding,
      digest: hmac({ method: "GET", path: "/state", nonce, payload: proofCore(payload) })
    }
  };
}

verifyProtectedFiles();
const { startTaskServer } = await import(pathToFileURL(path.join(appDir, "src", "server.mjs")).href);
startTaskServer({ authorizeNewGame, finalizeState });
