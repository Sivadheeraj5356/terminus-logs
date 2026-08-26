const std = @import("std");
const types = @import("types.zig");
const familyadj = @import("familyadj.zig");
const glyphpressure = @import("glyphpressure.zig");

pub fn baseMovePoints(archive: *const types.Archive, cell_id: []const u8) !f64 {
    const glyph_id = archive.solution.get(cell_id) orelse return types.ArchiveError.UnknownCell;
    const glyph = archive.glyphs.get(glyph_id) orelse return types.ArchiveError.MissingGlyph;
    const matches = try familyadj.matchingNeighborCount(archive, cell_id);
    const raw = glyph.weight + @as(f64, @floatFromInt(matches)) * 2.0;
    return types.roundHalfAwayFromZero(raw);
}

pub fn computeMovePoints(archive: *const types.Archive, cell_id: []const u8, move_index: usize) !f64 {
    const base = try baseMovePoints(archive, cell_id);
    const factor = try glyphpressure.pressureFactor(archive, cell_id, move_index);
    return types.roundHalfAwayFromZero(base * factor);
}
