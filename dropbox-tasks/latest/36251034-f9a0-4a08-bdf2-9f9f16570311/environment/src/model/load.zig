const std = @import("std");
const types = @import("types.zig");

pub fn readBundle(allocator: std.mem.Allocator, path: []const u8) !types.Bundle {
    const data = try std.fs.cwd().readFileAlloc(allocator, path, 8 * 1024 * 1024);
    defer allocator.free(data);

    var parsed = try std.json.parseFromSlice(
        std.json.Value,
        allocator,
        data,
        .{ .ignore_unknown_fields = true },
    );
    defer parsed.deinit();

    const root = parsed.value.object;

    const bundle_id = try allocator.dupe(u8, root.get("bundle_id").?.string);

    var custodians = std.StringArrayHashMap(types.Custodian).init(allocator);
    const cust_obj = root.get("custodians").?.object;
    var it = cust_obj.iterator();
    while (it.next()) |entry| {
        const cobj = entry.value_ptr.*.object;
        const pk = try allocator.dupe(u8, cobj.get("public_key_hex").?.string);
        const weight: i32 = @intCast(cobj.get("weight").?.integer);
        try custodians.put(try allocator.dupe(u8, entry.key_ptr.*), .{
            .public_key_hex = pk,
            .weight = weight,
        });
    }

    const revoked_val = root.get("revoked_custodians").?.array;
    var revoked = try allocator.alloc([]const u8, revoked_val.items.len);
    for (revoked_val.items, 0..) |item, i| {
        revoked[i] = try allocator.dupe(u8, item.string);
    }

    const queries_val = root.get("queries").?.array;
    var queries = try allocator.alloc(types.Query, queries_val.items.len);
    for (queries_val.items, 0..) |qval, qi| {
        const qobj = qval.object;
        const sigs_val = qobj.get("signatures").?.array;
        var sigs = try allocator.alloc(types.SignatureEntry, sigs_val.items.len);
        for (sigs_val.items, 0..) |sval, si| {
            const sobj = sval.object;
            sigs[si] = .{
                .custodian_id = try allocator.dupe(u8, sobj.get("custodian_id").?.string),
                .signature_hex = try allocator.dupe(u8, sobj.get("signature_hex").?.string),
            };
        }
        queries[qi] = .{
            .query_id = try allocator.dupe(u8, qobj.get("query_id").?.string),
            .eval_at = qobj.get("eval_at").?.integer,
            .artifact_sha256_hex = try allocator.dupe(u8, qobj.get("artifact_sha256_hex").?.string),
            .scope = try allocator.dupe(u8, qobj.get("scope").?.string),
            .release_epoch = qobj.get("release_epoch").?.integer,
            .min_weight = @intCast(qobj.get("min_weight").?.integer),
            .signatures = sigs,
        };
    }

    return .{
        .bundle_id = bundle_id,
        .custodians = custodians,
        .revoked_custodians = revoked,
        .queries = queries,
    };
}
