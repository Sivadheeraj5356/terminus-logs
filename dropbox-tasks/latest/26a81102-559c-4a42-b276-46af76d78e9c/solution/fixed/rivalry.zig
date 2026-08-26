const std = @import("std");
const types = @import("types.zig");
const familyadj = @import("familyadj.zig");
const sha256util = @import("sha256util.zig");

pub const RivalryPlayer = struct {
    player_id: []const u8,
    rivalry_points: f64,
};

pub const RivalryResult = struct {
    players: []RivalryPlayer,
    rivalry_digest: []const u8,
};

fn cellsAreNeighbors(archive: *const types.Archive, a: []const u8, b: []const u8) bool {
    for (archive.cells.items) |cell| {
        if (!std.mem.eql(u8, cell.id, a)) continue;
        for (cell.neighbors.items) |nb| {
            if (std.mem.eql(u8, nb, b)) return true;
        }
    }
    return false;
}

pub fn foldRivalry(allocator: std.mem.Allocator, archive: *const types.Archive) !RivalryResult {
    var totals = std.StringHashMap(f64).init(allocator);
    defer {
        var it = totals.iterator();
        while (it.next()) |entry| allocator.free(entry.key_ptr.*);
        totals.deinit();
    }

    for (archive.moves.items) |m| {
        const gop = try totals.getOrPut(m.player_id);
        if (!gop.found_existing) {
            gop.key_ptr.* = try allocator.dupe(u8, m.player_id);
            gop.value_ptr.* = 0;
        }
    }

    const moves = archive.moves.items;
    var i: usize = 0;
    while (i < moves.len) : (i += 1) {
        var j: usize = i + 1;
        while (j < moves.len) : (j += 1) {
            const a = moves[i];
            const b = moves[j];
            if (std.mem.eql(u8, a.player_id, b.player_id)) continue;
            const tick_diff = if (a.tick >= b.tick) a.tick - b.tick else b.tick - a.tick;
            if (tick_diff > 1) continue;
            if (!cellsAreNeighbors(archive, a.cell_id, b.cell_id)) continue;
            if (!familyadj.cellsShareFamily(archive, a.cell_id, b.cell_id)) continue;
            if (totals.getPtr(a.player_id)) |pa| pa.* += 0.5;
            if (totals.getPtr(b.player_id)) |pb| pb.* += 0.5;
        }
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

    var players = try allocator.alloc(RivalryPlayer, ids.items.len);
    var lines = std.ArrayList([]const u8).init(allocator);
    defer {
        for (lines.items) |l| allocator.free(l);
        lines.deinit();
    }

    for (ids.items, 0..) |id, idx| {
        const raw = totals.get(id) orelse 0;
        const pts = types.roundHalfAwayFromZero(raw);
        players[idx] = .{
            .player_id = try allocator.dupe(u8, id),
            .rivalry_points = pts,
        };
        const line = try std.fmt.allocPrint(allocator, "{s}|{d:.2}", .{ id, pts });
        try lines.append(line);
    }

    const digest = try sha256util.hashLines(allocator, lines.items);
    return .{ .players = players, .rivalry_digest = digest };
}

pub fn freeRivalryResult(allocator: std.mem.Allocator, result: RivalryResult) void {
    for (result.players) |p| allocator.free(p.player_id);
    allocator.free(result.players);
    allocator.free(result.rivalry_digest);
}
