const std = @import("std");
const types = @import("types.zig");

fn findCell(archive: *const types.Archive, id: []const u8) ?*const types.Cell {
    for (archive.cells.items) |*cell| {
        if (std.mem.eql(u8, cell.id, id)) return cell;
    }
    return null;
}

pub fn cellFamily(archive: *const types.Archive, cell_id: []const u8) ?[]const u8 {
    const glyph_id = archive.solution.get(cell_id) orelse return null;
    const glyph = archive.glyphs.get(glyph_id) orelse return null;
    return glyph.family;
}

pub fn cellsShareFamily(archive: *const types.Archive, a: []const u8, b: []const u8) bool {
    const fa = cellFamily(archive, a) orelse return false;
    const fb = cellFamily(archive, b) orelse return false;
    return std.mem.eql(u8, fa, fb);
}

pub fn matchingNeighborCount(archive: *const types.Archive, cell_id: []const u8) !i32 {
    const cell = findCell(archive, cell_id) orelse return types.ArchiveError.UnknownCell;
    const played_family = cellFamily(archive, cell_id) orelse return types.ArchiveError.MissingGlyph;
    var count: i32 = 0;
    for (cell.neighbors.items) |nb| {
        const nb_family = cellFamily(archive, nb) orelse continue;
        if (std.mem.eql(u8, nb_family, played_family)) count += 1;
    }
    return count;
}
