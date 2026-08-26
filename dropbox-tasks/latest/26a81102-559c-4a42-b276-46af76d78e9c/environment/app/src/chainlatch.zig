const std = @import("std");
const sha256util = @import("sha256util.zig");

pub const CHAIN_TIP_PATH = "/app/var/match_chain_tip.txt";

pub fn readPriorTip(allocator: std.mem.Allocator) ![]u8 {
    const file = std.fs.cwd().openFile(CHAIN_TIP_PATH, .{}) catch {
        return try allocator.dupe(u8, "");
    };
    defer file.close();
    const data = try file.readToEndAlloc(allocator, 1024 * 1024);
    defer allocator.free(data);
    const trimmed = std.mem.trim(u8, data, " \t\r\n");
    return try allocator.dupe(u8, trimmed);
}

pub fn advanceChainLatch(
    allocator: std.mem.Allocator,
    prior: []const u8,
    playtest_seal: []const u8,
    rivalry_digest: []const u8,
) ![]u8 {
    const payload = try std.fmt.allocPrint(allocator, "{s}|{s}|{s}", .{ prior, playtest_seal, rivalry_digest });
    defer allocator.free(payload);
    const digest = try sha256util.hashBytes(allocator, payload);
    const file = try std.fs.cwd().createFile(CHAIN_TIP_PATH, .{ .truncate = true });
    defer file.close();
    try file.writeAll(digest);
    try file.writeAll("\n");
    return digest;
}
