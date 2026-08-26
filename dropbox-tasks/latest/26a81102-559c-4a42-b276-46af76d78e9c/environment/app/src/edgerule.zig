const std = @import("std");
const types = @import("types.zig");
const familyadj = @import("familyadj.zig");

pub fn isFamilyDashedEdge(archive: *const types.Archive, a: []const u8, b: []const u8) bool {
    return familyadj.cellsShareFamily(archive, a, b);
}
