const std = @import("std");
const types = @import("../model/types.zig");

fn writeJsonString(w: anytype, text: []const u8) !void {
    try w.writeByte('"');
    for (text) |c| {
        switch (c) {
            '\\', '"', => {
                try w.writeByte('\\');
                try w.writeByte(c);
            },
            else => try w.writeByte(c),
        }
    }
    try w.writeByte('"');
}

pub fn writeReport(allocator: std.mem.Allocator, path: []const u8, report: types.Report) !void {
    var buf: std.ArrayListUnmanaged(u8) = .{};
    defer buf.deinit(allocator);
    const w = buf.writer(allocator);

    try w.writeAll("{\n");
    try w.writeAll("  \"bundle_id\": ");
    try writeJsonString(w, report.bundle_id);
    try w.writeAll(",\n  \"eval_profile\": ");
    try writeJsonString(w, report.eval_profile);
    try w.writeAll(",\n  \"results\": [\n");
    for (report.results, 0..) |row, idx| {
        try w.writeAll("    {\n");
        try w.writeAll("      \"query_id\": ");
        try writeJsonString(w, row.query_id);
        try w.writeAll(",\n      \"decision\": ");
        try writeJsonString(w, row.decision);
        try w.writeAll(",\n      \"reason\": ");
        try writeJsonString(w, row.reason);
        try w.print(",\n      \"quorum_weight\": {d},\n", .{row.quorum_weight});
        try w.print("      \"signatures_verified\": {d},\n", .{row.signatures_verified});
        try w.print("      \"unique_custodians\": {d}\n", .{row.unique_custodians});
        if (idx + 1 == report.results.len) {
            try w.writeAll("    }\n");
        } else {
            try w.writeAll("    },\n");
        }
    }
    try w.writeAll("  ],\n  \"stats\": {\n");
    try w.print("    \"queries_total\": {d},\n", .{report.stats.queries_total});
    try w.print("    \"allowed\": {d},\n", .{report.stats.allowed});
    try w.print("    \"denied\": {d},\n", .{report.stats.denied});
    try w.print("    \"signature_failures\": {d},\n", .{report.stats.signature_failures});
    try w.print("    \"quorum_failures\": {d},\n", .{report.stats.quorum_failures});
    try w.print("    \"revoked_hits\": {d}\n", .{report.stats.revoked_hits});
    try w.writeAll("  },\n  \"state_digest\": ");
    try writeJsonString(w, report.state_digest);
    try w.writeAll("\n}\n");

    try std.fs.cwd().writeFile(.{ .sub_path = path, .data = buf.items });
}
