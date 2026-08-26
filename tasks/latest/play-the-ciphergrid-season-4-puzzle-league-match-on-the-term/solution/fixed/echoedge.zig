const std = @import("std");
const types = @import("types.zig");
const familyadj = @import("familyadj.zig");

fn cellOnTape(archive: *const types.Archive, cell_id: []const u8) bool {
    for (archive.moves.items) |m| {
        if (std.mem.eql(u8, m.cell_id, cell_id)) return true;
    }
    return false;
}

pub fn isEchoDottedEdge(archive: *const types.Archive, a: []const u8, b: []const u8) bool {
    if (!familyadj.cellsShareFamily(archive, a, b)) return false;
    return cellOnTape(archive, a) and cellOnTape(archive, b);
}
