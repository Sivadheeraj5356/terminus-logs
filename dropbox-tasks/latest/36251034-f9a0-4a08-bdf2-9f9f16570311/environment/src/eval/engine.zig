const std = @import("std");
const types = @import("../model/types.zig");

pub fn evaluateStub(allocator: std.mem.Allocator, bundle: types.Bundle) !types.Report {
    var results = try allocator.alloc(types.ResultRow, bundle.queries.len);
    for (bundle.queries, 0..) |q, i| {
        results[i] = .{
            .query_id = try allocator.dupe(u8, q.query_id),
            .decision = try allocator.dupe(u8, "deny"),
            .reason = try allocator.dupe(u8, "signature_invalid"),
            .quorum_weight = 0,
            .signatures_verified = 0,
            .unique_custodians = @intCast(q.signatures.len),
        };
    }
    return .{
        .bundle_id = try allocator.dupe(u8, bundle.bundle_id),
        .eval_profile = try allocator.dupe(u8, "artifact-quorum-v1"),
        .results = results,
        .stats = .{
            .queries_total = @intCast(bundle.queries.len),
            .allowed = 0,
            .denied = @intCast(bundle.queries.len),
            .signature_failures = @intCast(bundle.queries.len),
            .quorum_failures = 0,
            .revoked_hits = 0,
        },
        .state_digest = try allocator.dupe(u8, "00"),
    };
}
