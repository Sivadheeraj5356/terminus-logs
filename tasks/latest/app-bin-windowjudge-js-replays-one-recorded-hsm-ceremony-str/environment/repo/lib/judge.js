"use strict";

function asInt(v) {
  if (typeof v === "number" && Number.isFinite(v)) return Math.trunc(v);
  return 0;
}

function asFloat(v) {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  return 0;
}

function str(v) {
  if (v === null || v === undefined) return "";
  return String(v);
}

function list(v) {
  if (v === null || v === undefined) return [];
  return v;
}

const ACTOR_FIELDS = ["key", "package", "sensor", "player"];

function actorOf(x) {
  for (const k of ACTOR_FIELDS) {
    if (x[k] !== undefined && x[k] !== null) return str(x[k]);
  }
  return "";
}

// Placeholder implementation: treats matching events as instantaneous and
// ignores deferred confirmations, freezes, and same-tick deadline ordering.
function computeIntervals(input) {
  const out = [];
  const until = asInt(input.until);
  for (const ev of list(input.events)) {
    const at = asInt(ev.at);
    switch (str(ev.op)) {
      case "report":
        if (ev.compromised === true) {
          out.push({ key: str(ev.key), start: at, end: until, reason: "confirmed_compromise" });
        }
        break;
      case "artifact":
        if (ev.ready === true) {
          out.push({ package: str(ev.package), start: at, end: until, reason: "cache_admitted" });
        }
        break;
      case "reading":
        if (typeof ev.value === "number" && ev.value > 0) {
          out.push({ sensor: str(ev.sensor), start: at, end: until, reason: "hysteresis_alarm" });
        }
        break;
      case "turn":
        out.push({ player: str(ev.player), start: at, end: until, reason: "flag_fall" });
        break;
      default:
        break;
    }
  }
  return out;
}

module.exports = { computeIntervals, asInt, asFloat, str, list, actorOf };
