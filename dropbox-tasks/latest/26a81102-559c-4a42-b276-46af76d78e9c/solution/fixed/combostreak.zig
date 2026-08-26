const std = @import("std");
const types = @import("types.zig");
const familyadj = @import("familyadj.zig");
const sha256util = @import("sha256util.zig");

pub const ComboPlayer = struct {
    player_id: []const u8,
    combo_points: f64,
    max_streak: i32,
};

pub const ComboResult = struct {
    players: []ComboPlayer,
    combo_digest: []const u8,
};

const MoveRef = struct {
    tick: i32,
    cell_id: []const u8,
};

fn moveLess(_: void, a: MoveRef, b: MoveRef) bool {
    if (a.tick != b.tick) return a.tick < b.tick;
    return std.mem.order(u8, a.cell_id, b.cell_id) == .lt;
}

pub fn foldCombo(allocator: std.mem.Allocator, archive: *const types.Archive) !ComboResult {
    var by_player = std.StringHashMap(std.ArrayList(MoveRef)).init(allocator);
    defer {
        var it = by_player.iterator();
        while (it.next()) |entry| {
            allocator.free(entry.key_ptr.*);
            entry.value_ptr.deinit();
        }
        by_player.deinit();
    }

    for (archive.moves.items) |move| {
        const gop = try by_player.getOrPut(try allocator.dupe(u8, move.player_id));
        if (!gop.found_existing) gop.value_ptr.* = std.ArrayList(MoveRef).init(allocator);
        try gop.value_ptr.append(.{ .tick = move.tick, .cell_id = move.cell_id });
    }

    var ids = std.ArrayList([]const u8).init(allocator);
    defer ids.deinit();
    var pit = by_player.iterator();
    while (pit.next()) |entry| try ids.append(entry.key_ptr.*);
    std.mem.sort([]const u8, ids.items, {}, struct {
        fn less(_: void, a: []const u8, b: []const u8) bool {
            return std.mem.order(u8, a, b) == .lt;
        }
    }.less);

    var players = try allocator.alloc(ComboPlayer, ids.items.len);
    var lines = std.ArrayList([]const u8).init(allocator);
    defer {
        for (lines.items) |l| allocator.free(l);
        lines.deinit();
    }

    for (ids.items, 0..) |id, i| {
        const bucket = by_player.getPtr(id).?;
        std.mem.sort(MoveRef, bucket.items, {}, moveLess);
        var raw: f64 = 0.0;
        var streak: i32 = 0;
        var max_streak: i32 = 0;
        var prev_family: ?[]const u8 = null;
        for (bucket.items) |m| {
            const fam = familyadj.cellFamily(archive, m.cell_id) orelse {
                streak = 1;
                prev_family = null;
                if (streak > max_streak) max_streak = streak;
                continue;
            };
            if (prev_family) |pf| {
                if (std.mem.eql(u8, pf, fam)) {
                    streak += 1;
                    raw += 0.25 * @as(f64, @floatFromInt(streak - 1));
                } else {
                    streak = 1;
                }
            } else {
                streak = 1;
            }
            prev_family = fam;
            if (streak > max_streak) max_streak = streak;
        }
        const combo_points = types.roundHalfAwayFromZero(raw);
        players[i] = .{
            .player_id = try allocator.dupe(u8, id),
            .combo_points = combo_points,
            .max_streak = max_streak,
        };
        const line = try std.fmt.allocPrint(allocator, "{s}|{d:.2}|{d}", .{ id, combo_points, max_streak });
        try lines.append(line);
    }

    const digest = try sha256util.hashLines(allocator, lines.items);
    return .{ .players = players, .combo_digest = digest };
}

pub fn freeComboResult(allocator: std.mem.Allocator, result: ComboResult) void {
    for (result.players) |p| allocator.free(p.player_id);
    allocator.free(result.players);
    allocator.free(result.combo_digest);
}
