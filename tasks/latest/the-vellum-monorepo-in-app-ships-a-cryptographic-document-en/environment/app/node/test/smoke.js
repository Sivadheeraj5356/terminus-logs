"use strict";

// Developer smoke check for the Node source package (run by dev-check).
const assert = require("assert");
const vellum = require("../src/index.js");

const ident = vellum.identity();
for (const key of ["version", "revision", "capabilities", "release_id"]) {
  assert.ok(key in ident, "missing identity field " + key);
}
const digest = vellum.canonicalDigest({ title: "Vellum", count: 3 });
assert.strictEqual(digest.length, 64, "digest should be 64 hex chars");
console.log("node smoke ok:", digest);
