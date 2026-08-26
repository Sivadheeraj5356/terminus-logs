"use strict";

const { execFileSync } = require("child_process");
const path = require("path");

function binaryPath() {
  if (process.env.VELLUM_CLI) {
    return process.env.VELLUM_CLI;
  }
  return path.join(__dirname, "bin", "vellum-cli");
}

function run(args) {
  return execFileSync(binaryPath(), args, { encoding: "utf8" }).trim();
}

function identity() {
  return JSON.parse(run(["identity"]));
}

function canonicalDigest(document) {
  const payload =
    typeof document === "string" ? document : JSON.stringify(document);
  return run(["digest", payload]);
}

module.exports = { identity, canonicalDigest };
