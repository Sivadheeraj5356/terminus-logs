const std = @import("std");
const types = @import("model/types.zig");
const load = @import("model/load.zig");
const engine = @import("eval/engine.zig");
const compose = @import("report/compose.zig");

pub fn main() !void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    var args = try std.process.argsWithAllocator(allocator);
    defer args.deinit();
    _ = args.next();

    var bundle_path: ?[]const u8 = null;
    var output_path: ?[]const u8 = null;
    while (args.next()) |arg| {
        if (std.mem.eql(u8, arg, "--bundle")) {
            bundle_path = args.next();
        } else if (std.mem.eql(u8, arg, "--output")) {
            output_path = args.next();
        }
    }
    const bundle_file = bundle_path orelse return error.MissingBundle;
    const out_file = output_path orelse return error.MissingOutput;

    var bundle = try load.readBundle(allocator, bundle_file);
    defer bundle.deinit(allocator);

    var report = try engine.evaluateStub(allocator, bundle);
    defer report.deinit(allocator);

    try compose.writeReport(allocator, out_file, report);
}

test "root import" {
    _ = types;
    _ = load;
    _ = engine;
    _ = compose;
}
