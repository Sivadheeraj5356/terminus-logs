const std = @import("std");
const types = @import("types.zig");

pub const RivalryPlayer = struct {
    player_id: []const u8,
    rivalry_points: f64,
};

pub const RivalryResult = struct {
    players: []RivalryPlayer,
    rivalry_digest: []const u8,
};

/// Cross-player orthogonal family clashes within one tick window.
pub fn foldRivalry(allocator: std.mem.Allocator, archive: *const types.Archive) !RivalryResult {
    _ = allocator;
    _ = archive;
    return error.RivalryIncomplete;
}

pub fn freeRivalryResult(allocator: std.mem.Allocator, result: RivalryResult) void {
    _ = allocator;
    _ = result;
}
