const std = @import("std");
const types = @import("types.zig");
const edgerule = @import("edgerule.zig");
const echoedge = @import("echoedge.zig");

fn cmpStr(_: void, a: []const u8, b: []const u8) bool {
    return std.mem.order(u8, a, b) == .lt;
}

fn orientedEdge(a: []const u8, b: []const u8) struct { []const u8, []const u8 } {
    if (std.mem.order(u8, a, b) == .lt) return .{ a, b };
    return .{ b, a };
}

pub fn buildDot(allocator: std.mem.Allocator, archive: *const types.Archive) ![]u8 {
    var buf = std.ArrayList(u8).init(allocator);
    errdefer buf.deinit();
    const w = buf.writer();
    try w.writeAll("digraph ciphergrid {\n");

    var cell_ids = std.ArrayList([]const u8).init(allocator);
    defer cell_ids.deinit();
    for (archive.cells.items) |cell| try cell_ids.append(cell.id);
    std.mem.sort([]const u8, cell_ids.items, {}, cmpStr);

    for (cell_ids.items) |id| {
        try w.print("  \"{s}\";\n", .{id});
    }

    var seen_adj = std.StringHashMap(void).init(allocator);
    defer seen_adj.deinit();

    for (archive.cells.items) |cell| {
        for (cell.neighbors.items) |nb| {
            const edge = orientedEdge(cell.id, nb);
            const key = try std.fmt.allocPrint(allocator, "{s}->{s}", .{ edge[0], edge[1] });
            const gop = try seen_adj.getOrPut(key);
            if (gop.found_existing) {
                allocator.free(key);
                continue;
            }
            try w.print("  \"{s}\" -> \"{s}\";\n", .{ edge[0], edge[1] });
        }
    }

    var seen_family = std.StringHashMap(void).init(allocator);
    defer seen_family.deinit();

    for (archive.cells.items) |cell| {
        for (cell.neighbors.items) |nb| {
            if (!edgerule.isFamilyDashedEdge(archive, cell.id, nb)) continue;
            const edge = orientedEdge(cell.id, nb);
            const key = try std.fmt.allocPrint(allocator, "f:{s}->{s}", .{ edge[0], edge[1] });
            const gop = try seen_family.getOrPut(key);
            if (gop.found_existing) {
                allocator.free(key);
                continue;
            }
            try w.print("  \"{s}\" -> \"{s}\" [style=dashed];\n", .{ edge[0], edge[1] });
        }
    }

    var seen_echo = std.StringHashMap(void).init(allocator);
    defer seen_echo.deinit();

    for (archive.cells.items) |cell| {
        for (cell.neighbors.items) |nb| {
            if (!echoedge.isEchoDottedEdge(archive, cell.id, nb)) continue;
            const edge = orientedEdge(cell.id, nb);
            const key = try std.fmt.allocPrint(allocator, "e:{s}->{s}", .{ edge[0], edge[1] });
            const gop = try seen_echo.getOrPut(key);
            if (gop.found_existing) {
                allocator.free(key);
                continue;
            }
            try w.print("  \"{s}\" -> \"{s}\" [style=dotted];\n", .{ edge[0], edge[1] });
        }
    }

    try w.writeAll("}\n");
    return buf.toOwnedSlice();
}
