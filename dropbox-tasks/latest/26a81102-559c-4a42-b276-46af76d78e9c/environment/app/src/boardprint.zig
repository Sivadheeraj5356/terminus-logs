const std = @import("std");
const types = @import("types.zig");
const sha256util = @import("sha256util.zig");

pub fn boardFingerprint(allocator: std.mem.Allocator, archive: *const types.Archive) ![]u8 {
    var ids = std.ArrayList([]const u8).init(allocator);
    defer ids.deinit();
    for (archive.cells.items) |cell| try ids.append(cell.id);
    std.mem.sort([]const u8, ids.items, {}, struct {
        fn less(_: void, a: []const u8, b: []const u8) bool {
            return std.mem.order(u8, a, b) == .lt;
        }
    }.less);

    var lines = std.ArrayList([]const u8).init(allocator);
    defer {
        for (lines.items) |l| allocator.free(l);
        lines.deinit();
    }

    for (ids.items) |id| {
        var cell_ptr: ?*const types.Cell = null;
        for (archive.cells.items) |*cell| {
            if (std.mem.eql(u8, cell.id, id)) {
                cell_ptr = cell;
                break;
            }
        }
        const cell = cell_ptr orelse return types.ArchiveError.UnknownCell;
        const glyph_id = archive.solution.get(id) orelse return types.ArchiveError.UnknownCell;
        const glyph = archive.glyphs.get(glyph_id) orelse return types.ArchiveError.MissingGlyph;
        const deg = cell.neighbors.items.len;
        const line = try std.fmt.allocPrint(allocator, "{s}|{s}|{s}|{d}", .{ id, glyph_id, glyph.family, deg });
        try lines.append(line);
    }
    return sha256util.hashLines(allocator, lines.items);
}
