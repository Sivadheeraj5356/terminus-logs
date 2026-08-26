const std = @import("std");
const matchplay = @import("matchplay.zig");

fn usage() void {
    const msg =
        \\cipherleague score --archive DIR --out REPORT.json
    ;
    std.io.getStdErr().writer().writeAll(msg) catch {};
}

fn findFlag(args: []const []const u8, name: []const u8) ?[]const u8 {
    var i: usize = 0;
    while (i < args.len) : (i += 1) {
        if (std.mem.eql(u8, args[i], name)) {
            if (i + 1 < args.len) return args[i + 1];
            return null;
        }
        const arg = args[i];
        if (std.mem.startsWith(u8, arg, name) and arg.len > name.len and arg[name.len] == '=') {
            return arg[name.len + 1 ..];
        }
    }
    return null;
}

fn cmdScore(allocator: std.mem.Allocator, args: []const []const u8) !void {
    const archive = findFlag(args, "--archive") orelse {
        try std.io.getStdErr().writer().writeAll("missing --archive\n");
        std.process.exit(1);
    };
    const out_path = findFlag(args, "--out") orelse {
        try std.io.getStdErr().writer().writeAll("missing --out\n");
        std.process.exit(1);
    };
    const json = try matchplay.evaluateArchive(allocator, archive);
    defer allocator.free(json);
    const file = try std.fs.cwd().createFile(out_path, .{ .truncate = true });
    defer file.close();
    try file.writeAll(json);
    try file.writeAll("\n");
}

pub fn main() !void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    const all = try std.process.argsAlloc(allocator);
    defer std.process.argsFree(allocator, all);
    if (all.len < 2) {
        usage();
        std.process.exit(1);
    }

    const cmd = all[1];
    if (std.mem.eql(u8, cmd, "score")) {
        try cmdScore(allocator, all[2..]);
        return;
    }

    usage();
    std.process.exit(1);
}
