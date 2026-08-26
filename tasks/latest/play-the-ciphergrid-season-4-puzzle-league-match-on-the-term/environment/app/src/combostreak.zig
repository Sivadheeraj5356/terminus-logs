const std = @import("std");
const types = @import("types.zig");

pub const ComboPlayer = struct {
    player_id: []const u8,
    combo_points: f64,
    max_streak: i32,
};

pub const ComboResult = struct {
    players: []ComboPlayer,
    combo_digest: []const u8,
};

/// Fold per-player family streak bonuses and the combo digest.
pub fn foldCombo(allocator: std.mem.Allocator, archive: *const types.Archive) !ComboResult {
    _ = allocator;
    _ = archive;
    return error.ComboStreakIncomplete;
}

pub fn freeComboResult(allocator: std.mem.Allocator, result: ComboResult) void {
    _ = allocator;
    _ = result;
}
