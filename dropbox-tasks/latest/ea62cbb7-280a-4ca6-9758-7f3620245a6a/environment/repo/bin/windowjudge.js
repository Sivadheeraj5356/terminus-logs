#!/usr/bin/env node
"use strict";

const { readFileSync } = require("node:fs");
const { computeIntervals, asInt, actorOf } = require("../lib/judge.js");

function sortIntervals(xs) {
  xs.sort((a, b) => {
    const ai = actorOf(a);
    const aj = actorOf(b);
    if (ai === aj) return asInt(a.start) - asInt(b.start);
    return ai < aj ? -1 : ai > aj ? 1 : 0;
  });
}

function main() {
  const input = JSON.parse(readFileSync(0, "utf8"));
  const intervals = computeIntervals(input);
  sortIntervals(intervals);
  process.stdout.write(JSON.stringify({ intervals }) + "\n");
}

main();
