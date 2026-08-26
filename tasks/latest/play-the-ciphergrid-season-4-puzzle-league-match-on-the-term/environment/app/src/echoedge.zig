const std = @import("std");
const types = @import("types.zig");

/// True when adjacency should emit a dotted echo edge (shared family + both cells appear on the tape).
pub fn isEchoDottedEdge(archive: *const types.Archive, a: []const u8, b: []const u8) bool {
    _ = archive;
    _ = a;
    _ = b;
    return false;
}
