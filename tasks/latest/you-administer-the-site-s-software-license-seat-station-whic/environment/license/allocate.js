"use strict";

const { eligibleSeats } = require("./entitlement");

function planAllocation(events, inventory, rules, config) {
  const seats = (inventory && inventory.seats) || [];
  const seatById = new Map(seats.map((s) => [s.seatId, s]));
  const table = (rules && rules.entitlement) || {};

  const suspendedIds = new Set();
  const rowsById = new Map();
  const cancelled = new Set();

  for (const e of events) {
    if (e.type === "suspend") {
      if (seatById.has(e.seatId)) {
        suspendedIds.add(e.seatId);
        rowsById.set(e.id, { id: e.id, type: e.type, decision: "suspend-applied", seatId: e.seatId });
      } else {
        rowsById.set(e.id, { id: e.id, type: e.type, decision: "rejected", reason: "unknown-seat", seatId: e.seatId });
      }
    } else if (e.type === "restore") {
      const suspend = events.find((x) => x.id === e.suspendId);
      if (suspend && suspendedIds.has(suspend.seatId)) {
        suspendedIds.delete(suspend.seatId);
        rowsById.set(e.id, { id: e.id, type: e.type, decision: "restore-applied", suspendId: e.suspendId });
      } else {
        rowsById.set(e.id, { id: e.id, type: e.type, decision: "restore-ignored", suspendId: e.suspendId, reason: "no-active-suspension" });
      }
    } else if (e.type === "cancel") {
      const target = events.find((x) => x.id === e.target);
      if (target && (target.type === "request" || target.type === "cancel")) {
        if (target.type === "request") cancelled.add(e.target);
        rowsById.set(e.id, { id: e.id, type: e.type, decision: "cancel-applied", target: e.target });
      } else {
        rowsById.set(e.id, { id: e.id, type: e.type, decision: "cancel-ignored", target: e.target, reason: "invalid-target" });
      }
    } else if (e.type === "request") {
      if (!table[e.edition]) {
        rowsById.set(e.id, { id: e.id, type: e.type, decision: "rejected", requestId: e.requestId, reason: "unknown-edition" });
      } else {
        rowsById.set(e.id, { id: e.id, type: e.type, decision: "request-accepted", requestId: e.requestId, edition: e.edition });
      }
    }
  }

  for (const eventId of cancelled) {
    const row = rowsById.get(eventId);
    if (row && row.decision === "request-accepted") {
      const by = events.filter((e) => e.type === "cancel" && e.target === eventId).map((e) => e.id).sort();
      rowsById.set(eventId, { id: eventId, type: "request", decision: "cancelled", cancelledBy: by });
    }
  }

  const expired = seats.filter((s) => s.coveredThrough < config.allocationDate);
  const expiredIds = new Set(expired.map((s) => s.seatId));
  const usable = seats.filter((s) => !suspendedIds.has(s.seatId) && !expiredIds.has(s.seatId));
  const available = new Map(usable.map((s) => [s.seatId, s]));

  const requests = [];
  for (const e of events) {
    const row = rowsById.get(e.id);
    if (e.type === "request" && row && row.decision === "request-accepted") {
      requests.push({
        requestId: e.requestId,
        edition: e.edition,
        seatsNeeded: Number(e.seatsNeeded || 0),
        priority: Number(e.priority || 0),
      });
    }
  }

  const allocations = [];
  let allocatedSeats = 0;
  let prioritySum = 0;
  for (const request of requests) {
    prioritySum += request.priority;
    const elig = eligibleSeats(request, [...available.values()], rules, config)
      .slice()
      .sort((a, b) => (a.coveredThrough < b.coveredThrough ? -1 : a.coveredThrough > b.coveredThrough ? 1 : a.seatId < b.seatId ? -1 : 1));
    if (elig.length < request.seatsNeeded) continue;
    const take = elig.slice(0, request.seatsNeeded);
    for (const s of take) available.delete(s.seatId);
    allocations.push({ requestId: request.requestId, edition: request.edition, seatIds: take.map((s) => s.seatId).sort() });
    allocatedSeats += take.length;
  }

  const filledIds = new Set(allocations.flatMap((a) => a.seatIds));
  const unusedSeats = usable.map((s) => s.seatId).filter((id) => !filledIds.has(id)).sort();

  const eventRows = events.map((e) => rowsById.get(e.id)).filter(Boolean);
  const summary = {
    allocatedSeats,
    cancelledRequests: eventRows.filter((r) => r.decision === "cancelled").length,
    expiredSeats: expired.length,
    filledRequests: allocations.length,
    prioritySum,
    rejectedEvents: eventRows.filter((r) => r.decision === "rejected").length,
    requestCount: requests.length,
    suspendedSeats: suspendedIds.size,
    totalEvents: events.length,
    unfilledRequests: requests.length - allocations.length,
    usableSeats: usable.length,
  };

  return { events: eventRows, allocations, unusedSeats, summary };
}

module.exports = { planAllocation };
