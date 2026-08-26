const std = @import("std");

pub const SignatureEntry = struct {
    custodian_id: []const u8,
    signature_hex: []const u8,
};

pub const Query = struct {
    query_id: []const u8,
    eval_at: i64,
    artifact_sha256_hex: []const u8,
    scope: []const u8,
    release_epoch: i64,
    min_weight: i32,
    signatures: []SignatureEntry,
};

pub const Custodian = struct {
    public_key_hex: []const u8,
    weight: i32,
};

pub const Bundle = struct {
    bundle_id: []const u8,
    custodians: std.StringArrayHashMap(Custodian),
    revoked_custodians: []const []const u8,
    queries: []Query,

    pub fn deinit(self: *Bundle, allocator: std.mem.Allocator) void {
        var it = self.custodians.iterator();
        while (it.next()) |entry| {
            allocator.free(entry.key_ptr.*);
            allocator.free(entry.value_ptr.public_key_hex);
        }
        self.custodians.deinit();
        for (self.queries) |*q| {
            allocator.free(q.query_id);
            allocator.free(q.artifact_sha256_hex);
            allocator.free(q.scope);
            for (q.signatures) |*s| {
                allocator.free(s.custodian_id);
                allocator.free(s.signature_hex);
            }
            allocator.free(q.signatures);
        }
        allocator.free(self.queries);
        for (self.revoked_custodians) |r| allocator.free(r);
        allocator.free(self.revoked_custodians);
        allocator.free(self.bundle_id);
    }
};

pub const ResultRow = struct {
    query_id: []const u8,
    decision: []const u8,
    reason: []const u8,
    quorum_weight: i32,
    signatures_verified: i32,
    unique_custodians: i32,
};

pub const Stats = struct {
    queries_total: i32,
    allowed: i32,
    denied: i32,
    signature_failures: i32,
    quorum_failures: i32,
    revoked_hits: i32,
};

pub const Report = struct {
    bundle_id: []const u8,
    eval_profile: []const u8,
    results: []ResultRow,
    stats: Stats,
    state_digest: []const u8,

    pub fn deinit(self: *Report, allocator: std.mem.Allocator) void {
        allocator.free(self.bundle_id);
        allocator.free(self.eval_profile);
        for (self.results) |*r| {
            allocator.free(r.query_id);
            allocator.free(r.decision);
            allocator.free(r.reason);
        }
        allocator.free(self.results);
        allocator.free(self.state_digest);
    }
};
