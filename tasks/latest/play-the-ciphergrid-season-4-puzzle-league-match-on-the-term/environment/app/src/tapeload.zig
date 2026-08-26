const std = @import("std");
const types = @import("types.zig");

fn joinPath(allocator: std.mem.Allocator, dir: []const u8, leaf: []const u8) ![]u8 {
    if (std.mem.endsWith(u8, dir, "/")) {
        return try std.fmt.allocPrint(allocator, "{s}{s}", .{ dir, leaf });
    }
    return try std.fmt.allocPrint(allocator, "{s}/{s}", .{ dir, leaf });
}

fn readFile(allocator: std.mem.Allocator, path: []const u8) ![]u8 {
    const file = std.fs.cwd().openFile(path, .{}) catch return types.ArchiveError.FileNotFound;
    defer file.close();
    return file.readToEndAlloc(allocator, 16 * 1024 * 1024);
}

fn parseGlyphs(allocator: std.mem.Allocator, text: []const u8, glyphs: *std.StringHashMap(types.Glyph)) !void {
    var current_id: ?[]const u8 = null;
    var weight: f64 = 0;
    var family_buf: ?[]u8 = null;

    var lines = std.mem.splitScalar(u8, text, '\n');
    while (lines.next()) |raw| {
        const line = std.mem.trim(u8, raw, " \t\r");
        if (line.len == 0) continue;
        if (line[0] == '[' and std.mem.endsWith(u8, line, "]")) {
            if (current_id) |cid| {
                const fam = family_buf orelse return types.ArchiveError.InvalidArchive;
                try glyphs.put(try allocator.dupe(u8, cid), .{
                    .id = try allocator.dupe(u8, cid),
                    .weight = weight,
                    .family = fam,
                });
            }
            current_id = try allocator.dupe(u8, line[1 .. line.len - 1]);
            weight = 0;
            family_buf = null;
            continue;
        }
        if (std.mem.startsWith(u8, line, "weight")) {
            const eq = std.mem.indexOfScalar(u8, line, '=') orelse return types.ArchiveError.InvalidArchive;
            weight = try std.fmt.parseFloat(f64, std.mem.trim(u8, line[eq + 1 ..], " \t"));
        } else if (std.mem.startsWith(u8, line, "family")) {
            const eq = std.mem.indexOfScalar(u8, line, '=') orelse return types.ArchiveError.InvalidArchive;
            var val = std.mem.trim(u8, line[eq + 1 ..], " \t");
            if (val.len >= 2 and val[0] == '"' and val[val.len - 1] == '"') {
                val = val[1 .. val.len - 1];
            }
            family_buf = try allocator.dupe(u8, val);
        }
    }
    if (current_id) |cid| {
        const fam = family_buf orelse return types.ArchiveError.InvalidArchive;
        try glyphs.put(try allocator.dupe(u8, cid), .{
            .id = try allocator.dupe(u8, cid),
            .weight = weight,
            .family = fam,
        });
    }
}

fn findCell(archive: *const types.Archive, id: []const u8) ?*const types.Cell {
    for (archive.cells.items) |*cell| {
        if (std.mem.eql(u8, cell.id, id)) return cell;
    }
    return null;
}

pub fn loadArchive(allocator: std.mem.Allocator, root: []const u8) !types.Archive {
    var archive = types.Archive{
        .root = try allocator.dupe(u8, root),
        .cells = std.ArrayList(types.Cell).init(allocator),
        .solution = std.StringHashMap([]const u8).init(allocator),
        .glyphs = std.StringHashMap(types.Glyph).init(allocator),
        .moves = std.ArrayList(types.Move).init(allocator),
        .allocator = allocator,
    };
    errdefer archive.deinit();

    const cells_path = try joinPath(allocator, root, "cells.json");
    defer allocator.free(cells_path);
    const cells_text = try readFile(allocator, cells_path);
    defer allocator.free(cells_text);

    const parsed = try std.json.parseFromSlice(std.json.Value, allocator, cells_text, .{});
    defer parsed.deinit();
    const root_obj = parsed.value.object;
    const cells_arr = root_obj.get("cells") orelse return types.ArchiveError.InvalidArchive;
    if (cells_arr != .array) return types.ArchiveError.InvalidArchive;
    for (cells_arr.array.items) |item| {
        const obj = item.object;
        const id_val = obj.get("id") orelse return types.ArchiveError.InvalidArchive;
        const x_val = obj.get("x") orelse return types.ArchiveError.InvalidArchive;
        const y_val = obj.get("y") orelse return types.ArchiveError.InvalidArchive;
        const nb_val = obj.get("neighbors") orelse return types.ArchiveError.InvalidArchive;
        var neighbors = std.ArrayList([]const u8).init(allocator);
        for (nb_val.array.items) |nb| {
            try neighbors.append(try allocator.dupe(u8, nb.string));
        }
        try archive.cells.append(.{
            .id = try allocator.dupe(u8, id_val.string),
            .x = @intCast(x_val.integer),
            .y = @intCast(y_val.integer),
            .neighbors = neighbors,
        });
    }

    const sol_obj = root_obj.get("solution") orelse return types.ArchiveError.InvalidArchive;
    if (sol_obj != .object) return types.ArchiveError.InvalidArchive;
    var sol_it = sol_obj.object.iterator();
    while (sol_it.next()) |entry| {
        try archive.solution.put(try allocator.dupe(u8, entry.key_ptr.*), try allocator.dupe(u8, entry.value_ptr.string));
    }

    const glyphs_path = try joinPath(allocator, root, "glyphs.toml");
    defer allocator.free(glyphs_path);
    const glyphs_text = try readFile(allocator, glyphs_path);
    defer allocator.free(glyphs_text);
    try parseGlyphs(allocator, glyphs_text, &archive.glyphs);

    const moves_path = try joinPath(allocator, root, "moves.jsonl");
    defer allocator.free(moves_path);
    const moves_text = try readFile(allocator, moves_path);
    defer allocator.free(moves_text);
    var move_lines = std.mem.splitScalar(u8, moves_text, '\n');
    while (move_lines.next()) |raw| {
        const line = std.mem.trim(u8, raw, " \t\r");
        if (line.len == 0) continue;
        const row = try std.json.parseFromSlice(std.json.Value, allocator, line, .{});
        defer row.deinit();
        const obj = row.value.object;
        const player = obj.get("player_id") orelse return types.ArchiveError.InvalidArchive;
        const cell = obj.get("cell_id") orelse return types.ArchiveError.InvalidArchive;
        const tick = obj.get("tick") orelse return types.ArchiveError.InvalidArchive;
        try archive.moves.append(.{
            .player_id = try allocator.dupe(u8, player.string),
            .cell_id = try allocator.dupe(u8, cell.string),
            .tick = @intCast(tick.integer),
        });
    }

    _ = findCell;
    return archive;
}
