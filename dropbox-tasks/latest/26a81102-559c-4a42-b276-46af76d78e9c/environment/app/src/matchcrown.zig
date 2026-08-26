const std = @import("std");
const sha256util = @import("sha256util.zig");

pub fn computeMatchCrown(
    allocator: std.mem.Allocator,
    playtest_seal: []const u8,
    rivalry_digest: []const u8,
    match_chain_digest: []const u8,
) ![]u8 {
    const payload = try std.fmt.allocPrint(
        allocator,
        "{s}|{s}|{s}",
        .{ playtest_seal, rivalry_digest, match_chain_digest },
    );
    defer allocator.free(payload);
    return sha256util.hashBytes(allocator, payload);
}
