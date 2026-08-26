import http from "node:http";
import { pathToFileURL } from "node:url";
import { HOST, PORT } from "./config.mjs";
import { advanceGame, createGame, publicState, scenarioCatalog, scenarioIds } from "./game.mjs";

let activeRun = null;
let runSerial = 0;

function sendJson(response, status, payload) {
  const body = JSON.stringify(payload);
  response.writeHead(status, {
    "content-type": "application/json",
    "content-length": Buffer.byteLength(body)
  });
  response.end(body);
}

async function readJson(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  if (!chunks.length) return {};
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

function statePayload() {
  if (!activeRun) return { error: "no active safari census" };
  return {
    ...publicState(activeRun),
    server_info: {
      engine_revision: "safari-species-counting-v1",
      run_serial: runSerial,
      has_active_run: true
    }
  };
}

export function startTaskServer({ authorizeNewGame, finalizeState } = {}) {
  const authorize = authorizeNewGame || (() => true);
  const finalize = finalizeState || ((payload) => payload);
  const server = http.createServer(async (request, response) => {
    const url = new URL(request.url || "/", `http://${request.headers.host || "localhost"}`);
    try {
      if (request.method === "GET" && url.pathname === "/health") {
        return sendJson(response, 200, {
          ok: true,
          has_active_run: Boolean(activeRun),
          server_info: { engine_revision: "safari-species-counting-v1", run_serial: runSerial }
        });
      }
      if (request.method === "GET" && url.pathname === "/scenarios") {
        return sendJson(response, 200, { scenarios: scenarioCatalog() });
      }
      if (request.method === "POST" && url.pathname === "/new_game") {
        const payload = await readJson(request);
        if (!authorize({ request, body: payload })) {
          return sendJson(response, 403, { error: "verifier setup signature required" });
        }
        if (activeRun) return sendJson(response, 409, { error: "safari census already active" });
        const scenarioId = String(payload.scenario_id || "");
        const seed = Number(payload.seed);
        if (!scenarioIds().includes(scenarioId)) return sendJson(response, 400, { error: "unknown scenario_id" });
        if (!Number.isSafeInteger(seed) || seed < 0) {
          return sendJson(response, 400, { error: "seed must be a non-negative integer" });
        }
        activeRun = createGame(scenarioId, seed);
        runSerial += 1;
        return sendJson(response, 201, statePayload());
      }
      if (request.method === "GET" && url.pathname === "/state") {
        const payload = statePayload();
        return sendJson(response, activeRun ? 200 : 404, activeRun ? finalize(payload, request) : payload);
      }
      if (request.method === "POST" && url.pathname === "/act") {
        if (!activeRun) return sendJson(response, 404, { error: "no active safari census" });
        const result = advanceGame(activeRun, await readJson(request));
        return sendJson(response, result.ok ? 200 : 409, { ...statePayload(), action_result: result });
      }
      return sendJson(response, 404, { error: "route not found" });
    } catch (error) {
      return sendJson(response, 400, { error: error instanceof Error ? error.message : "request failed" });
    }
  });
  server.listen(PORT, HOST, () => {
    process.stdout.write(`safari runtime listening on http://${HOST}:${PORT}\n`);
  });
  return server;
}

const directEntry = process.argv[1] ? pathToFileURL(process.argv[1]).href : "";
if (import.meta.url === directEntry) startTaskServer();
