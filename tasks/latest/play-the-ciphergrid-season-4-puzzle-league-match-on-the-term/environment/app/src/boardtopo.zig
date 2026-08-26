const std = @import("std");
const types = @import("types.zig");
const dotwriter = @import("dotwriter.zig");
const dotinvoke = @import("dotinvoke.zig");

pub const TopoResult = struct {
    layout_digest: []const u8,
    topology_dot_path: []const u8,
};

fn slugFromArchive(archive_root: []const u8) []const u8 {
    var i = archive_root.len;
    while (i > 0) : (i -= 1) {
        const ch = archive_root[i - 1];
        if (ch == '/') return archive_root[i..];
    }
    return archive_root;
}

pub fn buildTopologyDigest(allocator: std.mem.Allocator, archive: *const types.Archive) !TopoResult {
    try std.fs.cwd().makePath(types.VAR_DIR);

    const dot_body = try dotwriter.buildDot(allocator, archive);
    defer allocator.free(dot_body);

    const slug = slugFromArchive(archive.root);
    const dot_path = try std.fmt.allocPrint(allocator, "{s}/ciphergrid_{s}.dot", .{ types.VAR_DIR, slug });
    defer allocator.free(dot_path);

    {
        const file = try std.fs.cwd().createFile(dot_path, .{ .truncate = true });
        defer file.close();
        try file.writeAll(dot_body);
    }

    const nodes = try dotinvoke.runDotPlain(allocator, dot_path);
    defer dotinvoke.freeNodes(allocator, nodes);

    const layout_digest = try dotinvoke.layoutDigestFromNodes(allocator, nodes);
    const path_copy = try allocator.dupe(u8, dot_path);
    return .{ .layout_digest = layout_digest, .topology_dot_path = path_copy };
}

pub fn freeTopoResult(allocator: std.mem.Allocator, result: TopoResult) void {
    allocator.free(result.layout_digest);
    allocator.free(result.topology_dot_path);
}
