#!/usr/bin/env bash
set -euo pipefail

cat > /app/license/parse.js <<'JS'
"use strict";

function parseLine(line) {
  const e = JSON.parse(line);
  if (!e.id || !e.type) throw new Error("event requires id and type");
  return e;
}

function readFeed(text) {
  return String(text || "")
    .split(/\r?\n/)
    .filter((l) => l.trim())
    .map(parseLine);
}

module.exports = { parseLine, readFeed };
JS

cat > /app/license/entitlement.js <<'JS'
"use strict";

function eligibleSeats(request, seats, rules, config) {
  const table = (rules && rules.entitlement) || {};
  const sources = table[request.edition];
  if (!sources) return [];
  const exactTiers = (config && config.exactEditionTiers) || [];
  const exact = request.tier != null && exactTiers.includes(request.tier);
  return seats.filter((s) => {
    if (request.activeUntil && !(s.coveredThrough > request.activeUntil)) return false;
    return exact ? s.edition === request.edition : sources.includes(s.edition);
  });
}

module.exports = { eligibleSeats };
JS

cat > /app/license/allocate.js <<'JS'
"use strict";

const { eligibleSeats } = require("./entitlement");

function settleCancels(events) {
  const byId = new Map(events.map((e) => [e.id, e]));
  const cancelable = (id) => {
    const t = byId.get(id);
    return Boolean(t && (t.type === "request" || t.type === "cancel"));
  };
  let active = new Map(events.map((e) => [e.id, true]));
  for (let pass = 0; pass < events.length + 2; pass += 1) {
    const cancelledBy = new Map();
    for (const e of events) {
      if (e.type === "cancel" && active.get(e.id) && cancelable(e.target)) {
        const list = cancelledBy.get(e.target) || [];
        list.push(e.id);
        cancelledBy.set(e.target, list);
      }
    }
    const next = new Map(events.map((e) => [e.id, !cancelledBy.has(e.id)]));
    let same = true;
    for (const e of events) if (next.get(e.id) !== active.get(e.id)) same = false;
    if (same) {
      return {
        active,
        cancelledBy: new Map([...cancelledBy.entries()].map(([k, v]) => [k, v.slice().sort()])),
      };
    }
    active = next;
  }
  throw new Error("cancels did not converge");
}

function settleFeed(events, seatById, table) {
  const byId = new Map(events.map((e) => [e.id, e]));
  const { active, cancelledBy } = settleCancels(events);
  const rows = new Map();
  const activeSuspensions = new Map();
  for (const e of events) {
    if (e.type === "suspend") {
      if (!seatById.has(e.seatId)) {
        rows.set(e.id, { id: e.id, type: e.type, decision: "rejected", reason: "unknown-seat", seatId: e.seatId });
      } else {
        activeSuspensions.set(e.id, e.seatId);
        rows.set(e.id, { id: e.id, type: e.type, decision: "suspend-applied", seatId: e.seatId });
      }
    } else if (e.type === "restore") {
      if (activeSuspensions.has(e.suspendId)) {
        activeSuspensions.delete(e.suspendId);
        rows.set(e.id, { id: e.id, type: e.type, decision: "restore-applied", suspendId: e.suspendId });
      } else {
        rows.set(e.id, { id: e.id, type: e.type, decision: "restore-ignored", suspendId: e.suspendId, reason: "no-active-suspension" });
      }
    } else if (e.type === "cancel") {
      if (!active.get(e.id)) {
        rows.set(e.id, { id: e.id, type: e.type, decision: "cancelled", cancelledBy: cancelledBy.get(e.id) || [] });
      } else {
        const t = byId.get(e.target);
        if (t && (t.type === "request" || t.type === "cancel")) {
          rows.set(e.id, { id: e.id, type: e.type, decision: "cancel-applied", target: e.target });
        } else {
          rows.set(e.id, { id: e.id, type: e.type, decision: "cancel-ignored", target: e.target, reason: "invalid-target" });
        }
      }
    } else if (e.type === "request") {
      if (!active.get(e.id)) {
        rows.set(e.id, { id: e.id, type: e.type, decision: "cancelled", cancelledBy: cancelledBy.get(e.id) || [] });
      } else if (!table[e.edition]) {
        rows.set(e.id, { id: e.id, type: e.type, decision: "rejected", requestId: e.requestId, reason: "unknown-edition" });
      } else {
        rows.set(e.id, { id: e.id, type: e.type, decision: "request-accepted", requestId: e.requestId, edition: e.edition });
      }
    }
  }
  return { rows, activeSuspensions };
}

function subsetsOfSize(list, size) {
  const out = [];
  const pick = [];
  function rec(start) {
    if (pick.length === size) {
      out.push(pick.slice());
      return;
    }
    for (let i = start; i <= list.length - (size - pick.length); i += 1) {
      pick.push(list[i]);
      rec(i + 1);
      pick.pop();
    }
  }
  if (size > 0 && size <= list.length) rec(0);
  return out;
}

function coverKey(seatIds, seatById) {
  return seatIds
    .map((id) => seatById.get(id))
    .map((s) => `${s.coveredThrough}|${s.seatId}`)
    .sort()
    .join(",");
}

function allocate(requests, usable, rules, config, seatById) {
  const options = requests.map((request) => {
    const elig = eligibleSeats(request, usable, rules, config).map((s) => s.seatId);
    return subsetsOfSize(elig, request.seatsNeeded);
  });
  let best = null;
  const chosen = new Map();
  function evaluate() {
    const filled = new Set(chosen.keys());
    let prioritySum = 0;
    const fitted = [];
    for (const [requestId, ids] of chosen) {
      const request = requests.find((r) => r.requestId === requestId);
      prioritySum += request.priority;
      fitted.push(...ids);
    }
    const pattern = requests.map((r) => (filled.has(r.requestId) ? "1" : "0")).join("");
    const cand = {
      alloc: new Map([...chosen].map(([k, v]) => [k, v.slice().sort()])),
      count: filled.size,
      prioritySum,
      pattern,
      cover: coverKey(fitted, seatById),
      allocKey: requests
        .map((r) => (chosen.get(r.requestId) || []).slice().sort().join("+"))
        .join("|"),
    };
    if (
      best === null ||
      cand.count > best.count ||
      (cand.count === best.count && cand.prioritySum > best.prioritySum) ||
      (cand.count === best.count && cand.prioritySum === best.prioritySum && cand.pattern > best.pattern) ||
      (cand.count === best.count && cand.prioritySum === best.prioritySum && cand.pattern === best.pattern && cand.cover < best.cover) ||
      (cand.count === best.count && cand.prioritySum === best.prioritySum && cand.pattern === best.pattern && cand.cover === best.cover && cand.allocKey < best.allocKey)
    ) {
      best = cand;
    }
  }
  function rec(idx, available) {
    if (idx === requests.length) {
      evaluate();
      return;
    }
    rec(idx + 1, available);
    const request = requests[idx];
    for (const ids of options[idx]) {
      if (!ids.every((id) => available.has(id))) continue;
      const next = new Set(available);
      for (const id of ids) next.delete(id);
      chosen.set(request.requestId, ids);
      rec(idx + 1, next);
      chosen.delete(request.requestId);
    }
  }
  rec(0, new Set(usable.map((s) => s.seatId)));
  return best || { alloc: new Map(), count: 0, prioritySum: 0 };
}

function planAllocation(events, inventory, rules, config) {
  const seats = (inventory && inventory.seats) || [];
  const seatById = new Map(seats.map((s) => [s.seatId, s]));
  const table = (rules && rules.entitlement) || {};
  const { rows, activeSuspensions } = settleFeed(events, seatById, table);

  const suspendedIds = new Set(activeSuspensions.values());
  const expired = seats.filter((s) => s.coveredThrough <= config.allocationDate);
  const expiredIds = new Set(expired.map((s) => s.seatId));
  const usable = seats.filter((s) => !suspendedIds.has(s.seatId) && !expiredIds.has(s.seatId));

  const requests = [];
  for (const e of events) {
    if (e.type !== "request") continue;
    const row = rows.get(e.id);
    if (row && row.decision === "request-accepted") {
      requests.push({
        requestId: e.requestId,
        edition: e.edition,
        seatsNeeded: Number(e.seatsNeeded || 0),
        tier: e.tier,
        activeUntil: e.activeUntil,
        priority: Number(e.priority || 0),
      });
    }
  }

  const best = allocate(requests, usable, rules, config, seatById);

  const allocations = [];
  let allocatedSeats = 0;
  let prioritySum = 0;
  for (const request of requests) {
    const ids = best.alloc.get(request.requestId);
    if (!ids) continue;
    allocations.push({ requestId: request.requestId, edition: request.edition, seatIds: ids.slice().sort() });
    allocatedSeats += ids.length;
    prioritySum += request.priority;
  }
  const filledIds = new Set(allocations.flatMap((a) => a.seatIds));
  const unusedSeats = usable.map((s) => s.seatId).filter((id) => !filledIds.has(id)).sort();

  const eventRows = events.map((e) => rows.get(e.id)).filter(Boolean);
  const rejectedEvents = eventRows.filter((r) => r.decision === "rejected").length;
  const cancelledRequests = eventRows.filter((r) => r.type === "request" && r.decision === "cancelled").length;

  const summary = {
    allocatedSeats,
    cancelledRequests,
    expiredSeats: expired.length,
    filledRequests: allocations.length,
    prioritySum,
    rejectedEvents,
    requestCount: requests.length,
    suspendedSeats: suspendedIds.size,
    totalEvents: events.length,
    unfilledRequests: requests.length - allocations.length,
    usableSeats: usable.length,
  };

  return { events: eventRows, allocations, unusedSeats, summary };
}

module.exports = { planAllocation };
JS

cat > /app/license/cli.js <<'JS'
"use strict";

const fs = require("fs");
const path = require("path");
const { readFeed } = require("./parse");
const { planAllocation } = require("./allocate");

function main(argv) {
  if (argv.length !== 2) {
    console.error("usage: seat-allocate <feed.ndjson> <output.json>");
    process.exit(2);
  }
  const [feedPath, outputPath] = argv;
  const events = readFeed(fs.readFileSync(feedPath, "utf8"));
  const inventory = JSON.parse(fs.readFileSync("/app/data/seat_inventory.json", "utf8"));
  const rules = JSON.parse(fs.readFileSync("/app/data/entitlements.json", "utf8"));
  const config = JSON.parse(fs.readFileSync("/app/data/station_config.json", "utf8"));
  const report = planAllocation(events, inventory, rules, config);
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, JSON.stringify(report, null, 2) + "\n");
}

module.exports = { main };
JS

node /app/bin/seat-allocate /app/data/onboarding_requests.ndjson /app/out/allocation.json
cat /app/out/allocation.json
