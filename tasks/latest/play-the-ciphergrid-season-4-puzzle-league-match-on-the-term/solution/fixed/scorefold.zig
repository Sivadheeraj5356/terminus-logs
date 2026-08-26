const std = @import("std");
const types = @import("types.zig");
const movepoints = @import("movepoints.zig");

fn findCell(archive: *const types.Archive, id: []const u8) ?*const types.Cell {
    for (archive.cells.items) |*cell| {
        if (std.mem.eql(u8, cell.id, id)) return cell;
    }
    return null;
}

pub const ScoreResult = struct {
    players: []types.PlayerScore,
    season_score_digest: []const u8,
};

pub fn foldScores(allocator: std.mem.Allocator, archive: *const types.Archive) !ScoreResult {
    var totals = std.StringHashMap(struct { f64, i32 }).init(allocator);
    defer {
        var it = totals.iterator();
        while (it.next()) |entry| allocator.free(entry.key_ptr.*);
        totals.deinit();
    }

    for (archive.moves.items, 0..) |move, move_index| {
        _ = findCell(archive, move.cell_id) orelse return types.ArchiveError.UnknownCell;
        const pts = try movepoints.computeMovePoints(archive, move.cell_id, move_index);
        const gop = try totals.getOrPut(try allocator.dupe(u8, move.player_id));
        if (!gop.found_existing) gop.value_ptr.* = .{ 0, 0 };
        gop.value_ptr.*[0] += pts;
        gop.value_ptr.*[1] += 1;
    }

    var ids = std.ArrayList([]const u8).init(allocator);
    defer ids.deinit();
    var it = totals.iterator();
    while (it.next()) |entry| try ids.append(entry.key_ptr.*);
    std.mem.sort([]const u8, ids.items, {}, struct {
        fn less(_: void, a: []const u8, b: []const u8) bool {
            return std.mem.order(u8, a, b) == .lt;
        }
    }.less);

    var players = try allocator.alloc(types.PlayerScore, ids.items.len);
    var lines = std.ArrayList([]const u8).init(allocator);
    defer {
        for (lines.items) |l| allocator.free(l);
        lines.deinit();
    }

    for (ids.items, 0..) |id, i| {
        const bucket = totals.get(id).?;
        const total = types.roundHalfAwayFromZero(bucket[0]);
        players[i] = .{
            .player_id = try allocator.dupe(u8, id),
            .points = total,
            .moves = bucket[1],
            .combo_points = 0,
            .rivalry_points = 0,
        };
        const line = try std.fmt.allocPrint(allocator, "{s}|{d:.2}|{d}", .{ id, total, bucket[1] });
        try lines.append(line);
    }

    const sha256util = @import("sha256util.zig");
    const digest = try sha256util.hashLines(allocator, lines.items);
    return .{ .players = players, .season_score_digest = digest };
}

pub fn freeScoreResult(allocator: std.mem.Allocator, result: ScoreResult) void {
    for (result.players) |p| allocator.free(p.player_id);
    allocator.free(result.players);
    allocator.free(result.season_score_digest);
}
