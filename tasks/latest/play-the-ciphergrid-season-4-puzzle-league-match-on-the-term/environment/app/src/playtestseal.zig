const std = @import("std");
const sha256util = @import("sha256util.zig");

pub fn computePlaytestSeal(
    allocator: std.mem.Allocator,
    season_score_digest: []const u8,
    layout_digest: []const u8,
    combo_digest: []const u8,
    board_fingerprint: []const u8,
) ![]u8 {
    const payload = try std.fmt.allocPrint(
        allocator,
        "{s}|{s}|{s}|{s}",
        .{ season_score_digest, layout_digest, combo_digest, board_fingerprint },
    );
    defer allocator.free(payload);
    return sha256util.hashBytes(allocator, payload);
}
