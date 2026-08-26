#!/bin/bash
set -euo pipefail

cd /app
export PATH="/usr/local/zig:${PATH}"

cat > /app/src/crypto/canonical.zig <<'EOF'
const std = @import("std");

pub fn signingMessage(
    allocator: std.mem.Allocator,
    bundle_id: []const u8,
    query_id: []const u8,
    artifact_sha256_hex: []const u8,
    scope: []const u8,
    release_epoch: i64,
    min_weight: i32,
) ![]u8 {
    const lines: [7][]const u8 = .{
        "artifact-quorum-v1",
        bundle_id,
        query_id,
        artifact_sha256_hex,
        scope,
        try std.fmt.allocPrint(allocator, "{d}", .{release_epoch}),
        try std.fmt.allocPrint(allocator, "{d}", .{min_weight}),
    };
    defer {
        allocator.free(lines[5]);
        allocator.free(lines[6]);
    }
    var buf: std.ArrayListUnmanaged(u8) = .{};
    defer buf.deinit(allocator);
    for (lines, 0..) |line, idx| {
        try buf.appendSlice(allocator, line);
        if (idx + 1 < lines.len) try buf.append(allocator, '\n');
    }
    return try buf.toOwnedSlice(allocator);
}
EOF

cat > /app/src/eval/scope.zig <<'EOF'
const std = @import("std");

pub fn scopeWellFormed(scope: []const u8) bool {
    var parts = std.mem.splitScalar(u8, scope, '|');
    var count: usize = 0;
    while (parts.next()) |part| {
        if (part.len == 0) return false;
        count += 1;
    }
    return count == 3;
}
EOF

cat > /app/src/eval/time.zig <<'EOF'
const max_release_age_sec: i64 = 86400;
const max_future_skew_sec: i64 = 300;

pub fn epochFuture(eval_at: i64, release_epoch: i64) bool {
    return release_epoch > eval_at + max_future_skew_sec;
}

pub fn epochStale(eval_at: i64, release_epoch: i64) bool {
    return eval_at - release_epoch > max_release_age_sec;
}
EOF

cat > /app/src/eval/quorum.zig <<'EOF'
const std = @import("std");
const types = @import("../model/types.zig");
const canonical = @import("../crypto/canonical.zig");
const scope = @import("scope.zig");
const time = @import("time.zig");

fn decodeHex(allocator: std.mem.Allocator, hex: []const u8) ![]u8 {
    if (hex.len % 2 != 0) return error.BadHex;
    var out = try allocator.alloc(u8, hex.len / 2);
    errdefer allocator.free(out);
    for (0..hex.len / 2) |i| {
        out[i] = try std.fmt.parseInt(u8, hex[i * 2 .. i * 2 + 2], 16);
    }
    return out;
}

fn verifySignature(public_key_hex: []const u8, message: []const u8, signature_hex: []const u8, allocator: std.mem.Allocator) !bool {
    if (signature_hex.len != 128) return false;
    const pk_bytes = decodeHex(allocator, public_key_hex) catch return false;
    defer allocator.free(pk_bytes);
    const sig_bytes = decodeHex(allocator, signature_hex) catch return false;
    defer allocator.free(sig_bytes);
    if (pk_bytes.len != 32 or sig_bytes.len != 64) return false;
    var pk_arr: [32]u8 = undefined;
    var sig_arr: [64]u8 = undefined;
    @memcpy(pk_arr[0..], pk_bytes);
    @memcpy(sig_arr[0..], sig_bytes);
    const pk = std.crypto.sign.Ed25519.PublicKey.fromBytes(pk_arr) catch return false;
    const sig = std.crypto.sign.Ed25519.Signature.fromBytes(sig_arr);
    sig.verify(message, pk) catch return false;
    return true;
}

fn isRevoked(bundle: types.Bundle, custodian_id: []const u8) bool {
    for (bundle.revoked_custodians) |rid| {
        if (std.mem.eql(u8, rid, custodian_id)) return true;
    }
    return false;
}

fn uniqueCount(signatures: []types.SignatureEntry) i32 {
    var count: i32 = 0;
    for (signatures, 0..) |entry, i| {
        var seen_before = false;
        for (signatures[0..i]) |prior| {
            if (std.mem.eql(u8, prior.custodian_id, entry.custodian_id)) {
                seen_before = true;
                break;
            }
        }
        if (!seen_before) count += 1;
    }
    return count;
}

pub fn evaluateQuery(
    allocator: std.mem.Allocator,
    bundle: types.Bundle,
    query: types.Query,
) !types.ResultRow {
    const unique_custodians = uniqueCount(query.signatures);

    if (!scope.scopeWellFormed(query.scope)) {
        return makeRow(allocator, query.query_id, "deny", "scope_malformed", 0, 0, unique_custodians);
    }
    if (time.epochFuture(query.eval_at, query.release_epoch)) {
        return makeRow(allocator, query.query_id, "deny", "epoch_future", 0, 0, unique_custodians);
    }
    if (time.epochStale(query.eval_at, query.release_epoch)) {
        return makeRow(allocator, query.query_id, "deny", "epoch_stale", 0, 0, unique_custodians);
    }

    const msg = try canonical.signingMessage(
        allocator,
        bundle.bundle_id,
        query.query_id,
        query.artifact_sha256_hex,
        query.scope,
        query.release_epoch,
        query.min_weight,
    );
    defer allocator.free(msg);

    var seen = std.StringHashMap(void).init(allocator);
    defer seen.deinit();
    var verified_weight: i32 = 0;
    var verified_count: i32 = 0;

    for (query.signatures) |entry| {
        const gop = try seen.getOrPut(entry.custodian_id);
        if (gop.found_existing) {
            return makeRow(allocator, query.query_id, "deny", "duplicate_custodian", verified_weight, verified_count, unique_custodians);
        }

        const cust = bundle.custodians.get(entry.custodian_id) orelse {
            return makeRow(allocator, query.query_id, "deny", "unknown_custodian", verified_weight, verified_count, unique_custodians);
        };

        if (isRevoked(bundle, entry.custodian_id)) {
            return makeRow(allocator, query.query_id, "deny", "revoked_custodian", verified_weight, verified_count, unique_custodians);
        }

        const ok = try verifySignature(cust.public_key_hex, msg, entry.signature_hex, allocator);
        if (!ok) {
            return makeRow(allocator, query.query_id, "deny", "signature_invalid", verified_weight, verified_count, unique_custodians);
        }

        verified_count += 1;
        verified_weight += cust.weight;
    }

    if (verified_weight < query.min_weight) {
        return makeRow(allocator, query.query_id, "deny", "insufficient_quorum", verified_weight, verified_count, unique_custodians);
    }

    return makeRow(allocator, query.query_id, "allow", "quorum_ok", verified_weight, verified_count, unique_custodians);
}

fn makeRow(
    allocator: std.mem.Allocator,
    query_id: []const u8,
    decision: []const u8,
    reason: []const u8,
    quorum_weight: i32,
    signatures_verified: i32,
    unique_custodians: i32,
) !types.ResultRow {
    return .{
        .query_id = try allocator.dupe(u8, query_id),
        .decision = try allocator.dupe(u8, decision),
        .reason = try allocator.dupe(u8, reason),
        .quorum_weight = quorum_weight,
        .signatures_verified = signatures_verified,
        .unique_custodians = unique_custodians,
    };
}
EOF

cat > /app/src/report/digest.zig <<'EOF'
const std = @import("std");
const types = @import("../model/types.zig");

fn cmpQueryId(_: void, a: types.ResultRow, b: types.ResultRow) bool {
    return std.mem.order(u8, a.query_id, b.query_id) == .lt;
}

pub fn digestReport(allocator: std.mem.Allocator, results: []types.ResultRow, stats: types.Stats) ![]u8 {
    const sorted = try allocator.alloc(types.ResultRow, results.len);
    defer allocator.free(sorted);
    @memcpy(sorted, results);
    std.mem.sort(types.ResultRow, sorted, {}, cmpQueryId);

    var buf: std.ArrayListUnmanaged(u8) = .{};
    defer buf.deinit(allocator);
    const w = buf.writer(allocator);

    for (sorted) |row| {
        try w.print("{s}\t{s}\t{s}\t{d}\t{d}\t{d}\n", .{
            row.query_id,
            row.decision,
            row.reason,
            row.quorum_weight,
            row.signatures_verified,
            row.unique_custodians,
        });
    }
    try w.print("stats\t{d}\t{d}\t{d}\t{d}\t{d}\t{d}", .{
        stats.queries_total,
        stats.allowed,
        stats.denied,
        stats.signature_failures,
        stats.quorum_failures,
        stats.revoked_hits,
    });

    var digest_bytes: [32]u8 = undefined;
    std.crypto.hash.sha2.Sha256.hash(buf.items, &digest_bytes, .{});
    const hex_arr = std.fmt.bytesToHex(digest_bytes, .lower);
    return try allocator.dupe(u8, &hex_arr);
}
EOF

cat > /app/src/eval/engine.zig <<'EOF'
const std = @import("std");
const types = @import("../model/types.zig");
const quorum = @import("quorum.zig");
const digest = @import("../report/digest.zig");

fn cmpQueryId(_: void, a: types.ResultRow, b: types.ResultRow) bool {
    return std.mem.order(u8, a.query_id, b.query_id) == .lt;
}

pub fn evaluateStub(allocator: std.mem.Allocator, bundle: types.Bundle) !types.Report {
    return try evaluate(allocator, bundle);
}

pub fn evaluate(allocator: std.mem.Allocator, bundle: types.Bundle) !types.Report {
    var results = try allocator.alloc(types.ResultRow, bundle.queries.len);
    var stats = types.Stats{
        .queries_total = @intCast(bundle.queries.len),
        .allowed = 0,
        .denied = 0,
        .signature_failures = 0,
        .quorum_failures = 0,
        .revoked_hits = 0,
    };

    for (bundle.queries, 0..) |query, i| {
        const row = try quorum.evaluateQuery(allocator, bundle, query);
        results[i] = row;
        if (std.mem.eql(u8, row.decision, "allow")) {
            stats.allowed += 1;
        } else {
            stats.denied += 1;
        }
        if (std.mem.eql(u8, row.reason, "signature_invalid")) stats.signature_failures += 1;
        if (std.mem.eql(u8, row.reason, "insufficient_quorum")) stats.quorum_failures += 1;
        if (std.mem.eql(u8, row.reason, "revoked_custodian")) stats.revoked_hits += 1;
    }

    std.mem.sort(types.ResultRow, results, {}, cmpQueryId);
    const state_digest = try digest.digestReport(allocator, results, stats);

    return .{
        .bundle_id = try allocator.dupe(u8, bundle.bundle_id),
        .eval_profile = try allocator.dupe(u8, "artifact-quorum-v1"),
        .results = results,
        .stats = stats,
        .state_digest = state_digest,
    };
}
EOF

cat > /app/src/report/compose.zig <<'EOF'
const std = @import("std");
const types = @import("../model/types.zig");

fn writeJsonString(w: anytype, text: []const u8) !void {
    try w.writeByte('"');
    for (text) |c| {
        switch (c) {
            '\\', '"', => {
                try w.writeByte('\\');
                try w.writeByte(c);
            },
            else => try w.writeByte(c),
        }
    }
    try w.writeByte('"');
}

pub fn writeReport(allocator: std.mem.Allocator, path: []const u8, report: types.Report) !void {
    var buf: std.ArrayListUnmanaged(u8) = .{};
    defer buf.deinit(allocator);
    const w = buf.writer(allocator);

    try w.writeAll("{\n");
    try w.writeAll("  \"bundle_id\": ");
    try writeJsonString(w, report.bundle_id);
    try w.writeAll(",\n  \"eval_profile\": ");
    try writeJsonString(w, report.eval_profile);
    try w.writeAll(",\n  \"results\": [\n");
    for (report.results, 0..) |row, idx| {
        try w.writeAll("    {\n");
        try w.writeAll("      \"query_id\": ");
        try writeJsonString(w, row.query_id);
        try w.writeAll(",\n      \"decision\": ");
        try writeJsonString(w, row.decision);
        try w.writeAll(",\n      \"reason\": ");
        try writeJsonString(w, row.reason);
        try w.print(",\n      \"quorum_weight\": {d},\n", .{row.quorum_weight});
        try w.print("      \"signatures_verified\": {d},\n", .{row.signatures_verified});
        try w.print("      \"unique_custodians\": {d}\n", .{row.unique_custodians});
        if (idx + 1 == report.results.len) {
            try w.writeAll("    }\n");
        } else {
            try w.writeAll("    },\n");
        }
    }
    try w.writeAll("  ],\n  \"stats\": {\n");
    try w.print("    \"queries_total\": {d},\n", .{report.stats.queries_total});
    try w.print("    \"allowed\": {d},\n", .{report.stats.allowed});
    try w.print("    \"denied\": {d},\n", .{report.stats.denied});
    try w.print("    \"signature_failures\": {d},\n", .{report.stats.signature_failures});
    try w.print("    \"quorum_failures\": {d},\n", .{report.stats.quorum_failures});
    try w.print("    \"revoked_hits\": {d}\n", .{report.stats.revoked_hits});
    try w.writeAll("  },\n  \"state_digest\": ");
    try writeJsonString(w, report.state_digest);
    try w.writeAll("\n}\n");

    try std.fs.cwd().writeFile(.{ .sub_path = path, .data = buf.items });
}
EOF

/usr/local/zig/zig build -Doptimize=ReleaseSafe
cp /app/zig-out/bin/quorumgate /app/bin/quorumgate
mkdir -p /app/output

for bundle_dir in /app/data/bundles/*/; do
  bundle="${bundle_dir%/}/bundle.json"
  /app/bin/quorumgate --bundle "$bundle" --output /app/output/release_audit.json
done

echo "oracle build complete"
