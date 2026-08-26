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
