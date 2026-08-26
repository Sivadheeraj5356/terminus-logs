const std = @import("std");
const types = @import("types.zig");
const familyadj = @import("familyadj.zig");

pub fn unplayedSameFamilyCount(
    archive: *const types.Archive,
    family: []const u8,
    prior_move_count: usize,
) i32 {
    var played = std.StringHashMap(void).init(archive.allocator);
    defer {
        var it = played.keyIterator();
        while (it.next()) |_| {}
        played.deinit();
    }
    var i: usize = 0;
    while (i < prior_move_count and i < archive.moves.items.len) : (i += 1) {
        _ = played.put(archive.moves.items[i].cell_id, {}) catch {};
    }
    var count: i32 = 0;
    for (archive.cells.items) |cell| {
        const fam = familyadj.cellFamily(archive, cell.id) orelse continue;
        if (!std.mem.eql(u8, fam, family)) continue;
        if (played.contains(cell.id)) continue;
        count += 1;
    }
    return count;
}

pub fn pressureFactor(archive: *const types.Archive, cell_id: []const u8, prior_move_count: usize) !f64 {
    const fam = familyadj.cellFamily(archive, cell_id) orelse return types.ArchiveError.MissingGlyph;
    const remaining = unplayedSameFamilyCount(archive, fam, prior_move_count);
    return 1.0 + 0.05 * @as(f64, @floatFromInt(remaining));
}
