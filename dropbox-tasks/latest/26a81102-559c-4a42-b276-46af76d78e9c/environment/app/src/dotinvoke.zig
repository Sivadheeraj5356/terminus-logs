const std = @import("std");
const types = @import("types.zig");

pub fn runDotPlain(allocator: std.mem.Allocator, dot_path: []const u8) ![]types.LayoutNode {
    const argv = [_][]const u8{ "dot", "-Tplain", dot_path };
    var child = std.process.Child.init(&argv, allocator);
    child.stdout_behavior = .Pipe;
    child.stderr_behavior = .Pipe;
    try child.spawn();
    const stdout = try child.stdout.?.readToEndAlloc(allocator, 8 * 1024 * 1024);
    defer allocator.free(stdout);
    const stderr = try child.stderr.?.readToEndAlloc(allocator, 1024 * 1024);
    defer allocator.free(stderr);
    const term = try child.wait();
    switch (term) {
        .Exited => |code| {
            if (code != 0) {
                std.log.err("dot failed: {s}", .{stderr});
                return error.DotFailed;
            }
        },
        else => return error.DotFailed,
    }

    var nodes = std.ArrayList(types.LayoutNode).init(allocator);
    var lines = std.mem.splitScalar(u8, stdout, '\n');
    while (lines.next()) |raw| {
        const line = std.mem.trim(u8, raw, " \t\r");
        if (line.len == 0) continue;
        var it = std.mem.splitScalar(u8, line, ' ');
        const kind = it.next() orelse continue;
        if (!std.mem.eql(u8, kind, "node")) continue;
        const name = it.next() orelse continue;
        const xs = it.next() orelse continue;
        const ys = it.next() orelse continue;
        const x = try std.fmt.parseFloat(f64, xs);
        const y = try std.fmt.parseFloat(f64, ys);
        try nodes.append(.{
            .name = try allocator.dupe(u8, name),
            .x = x,
            .y = y,
        });
    }
    return nodes.toOwnedSlice();
}

pub fn layoutDigestFromNodes(allocator: std.mem.Allocator, nodes: []types.LayoutNode) ![]u8 {
    const sha256util = @import("sha256util.zig");
    var names = std.ArrayList([]const u8).init(allocator);
    defer names.deinit();
    for (nodes) |n| try names.append(n.name);
    std.mem.sort([]const u8, names.items, {}, struct {
        fn less(_: void, a: []const u8, b: []const u8) bool {
            return std.mem.order(u8, a, b) == .lt;
        }
    }.less);

    var lines = std.ArrayList([]const u8).init(allocator);
    defer {
        for (lines.items) |l| allocator.free(l);
        lines.deinit();
    }

    for (names.items) |name| {
        for (nodes) |n| {
            if (!std.mem.eql(u8, n.name, name)) continue;
            const rx = types.roundHalfAwayFromZero(n.x);
            const ry = types.roundHalfAwayFromZero(n.y);
            const line = try std.fmt.allocPrint(allocator, "{s}|{d:.2}|{d:.2}", .{ name, rx, ry });
            try lines.append(line);
        }
    }
    return sha256util.hashLines(allocator, lines.items);
}

pub fn freeNodes(allocator: std.mem.Allocator, nodes: []types.LayoutNode) void {
    for (nodes) |n| allocator.free(n.name);
    allocator.free(nodes);
}
