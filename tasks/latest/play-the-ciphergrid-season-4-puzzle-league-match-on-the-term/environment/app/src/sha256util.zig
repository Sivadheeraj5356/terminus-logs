const std = @import("std");
const Sha256 = std.crypto.hash.sha2.Sha256;

pub fn hashBytes(allocator: std.mem.Allocator, data: []const u8) ![]u8 {
    var digest: [Sha256.digest_length]u8 = undefined;
    Sha256.hash(data, &digest, .{});
    const hex = try allocator.alloc(u8, digest.len * 2);
    _ = std.fmt.bufPrint(hex, "{s}", .{std.fmt.fmtSliceHexLower(&digest)}) catch unreachable;
    return hex;
}

pub fn hashLines(allocator: std.mem.Allocator, lines: []const []const u8) ![]u8 {
    var joined = std.ArrayList(u8).init(allocator);
    defer joined.deinit();
    for (lines, 0..) |line, i| {
        if (i > 0) try joined.append('\n');
        try joined.appendSlice(line);
    }
    return hashBytes(allocator, joined.items);
}
