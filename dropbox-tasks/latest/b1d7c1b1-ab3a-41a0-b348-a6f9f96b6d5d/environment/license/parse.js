"use strict";

function parseLine(line) {
  return JSON.parse(line);
}

function readFeed(text) {
  return String(text || "")
    .split(/\r?\n/)
    .filter((l) => l.trim())
    .map(parseLine);
}

module.exports = { parseLine, readFeed };
