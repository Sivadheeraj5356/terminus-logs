const std = @import("std");
const types = @import("types.zig");

pub fn escapeJsonString(allocator: std.mem.Allocator, s: []const u8) ![]u8 {
    var out = std.ArrayList(u8).init(allocator);
    errdefer out.deinit();
    try out.append('"');
    for (s) |ch| {
        switch (ch) {
            '"' => try out.appendSlice("\\\""),
            '\\' => try out.appendSlice("\\\\"),
            '\n' => try out.appendSlice("\\n"),
            '\r' => try out.appendSlice("\\r"),
            '\t' => try out.appendSlice("\\t"),
            else => try out.append(ch),
        }
    }
    try out.append('"');
    return out.toOwnedSlice();
}

pub fn buildReportJson(allocator: std.mem.Allocator, report: types.EvalReport) ![]u8 {
    var buf = std.ArrayList(u8).init(allocator);
    errdefer buf.deinit();
    const w = buf.writer();
    const arch = try escapeJsonString(allocator, report.archive);
    defer allocator.free(arch);
    const layout = try escapeJsonString(allocator, report.layout_digest);
    defer allocator.free(layout);
    const season = try escapeJsonString(allocator, report.season_score_digest);
    defer allocator.free(season);
    const dot_path = try escapeJsonString(allocator, report.topology_dot_path);
    defer allocator.free(dot_path);
    const combo = try escapeJsonString(allocator, report.combo_digest);
    defer allocator.free(combo);
    const board = try escapeJsonString(allocator, report.board_fingerprint);
    defer allocator.free(board);
    const seal = try escapeJsonString(allocator, report.playtest_seal);
    defer allocator.free(seal);
    const rivalry = try escapeJsonString(allocator, report.rivalry_digest);
    defer allocator.free(rivalry);
    const chain = try escapeJsonString(allocator, report.match_chain_digest);
    defer allocator.free(chain);
    const crown = try escapeJsonString(allocator, report.match_crown);
    defer allocator.free(crown);

    try w.writeAll("{\"archive\":");
    try w.writeAll(arch);
    try w.print(",\"cell_count\":{d},\"move_count\":{d},\"players\":[", .{
        report.cell_count,
        report.move_count,
    });
    for (report.players, 0..) |p, i| {
        if (i > 0) try w.writeAll(",");
        const pid = try escapeJsonString(allocator, p.player_id);
        defer allocator.free(pid);
        const pts = try types.formatFixed2(allocator, p.points);
        defer allocator.free(pts);
        const combo_pts = try types.formatFixed2(allocator, p.combo_points);
        defer allocator.free(combo_pts);
        const riv_pts = try types.formatFixed2(allocator, p.rivalry_points);
        defer allocator.free(riv_pts);
        try w.print("{{\"player_id\":{s},\"points\":{s},\"moves\":{d},\"combo_points\":{s},\"rivalry_points\":{s}}}", .{
            pid,
            pts,
            p.moves,
            combo_pts,
            riv_pts,
        });
    }
    try w.writeAll("],\"layout_digest\":");
    try w.writeAll(layout);
    try w.writeAll(",\"season_score_digest\":");
    try w.writeAll(season);
    try w.writeAll(",\"topology_dot_path\":");
    try w.writeAll(dot_path);
    try w.writeAll(",\"combo_digest\":");
    try w.writeAll(combo);
    try w.writeAll(",\"board_fingerprint\":");
    try w.writeAll(board);
    try w.writeAll(",\"playtest_seal\":");
    try w.writeAll(seal);
    try w.writeAll(",\"rivalry_digest\":");
    try w.writeAll(rivalry);
    try w.writeAll(",\"match_chain_digest\":");
    try w.writeAll(chain);
    try w.writeAll(",\"match_crown\":");
    try w.writeAll(crown);
    try w.writeAll("}");
    return buf.toOwnedSlice();
}

pub fn buildDigestJson(
    allocator: std.mem.Allocator,
    layout_digest: []const u8,
    season_digest: []const u8,
    combo_digest: []const u8,
    board_fingerprint: []const u8,
    playtest_seal: []const u8,
    rivalry_digest: []const u8,
    match_chain_digest: []const u8,
    match_crown: []const u8,
) ![]u8 {
    const layout = try escapeJsonString(allocator, layout_digest);
    defer allocator.free(layout);
    const season = try escapeJsonString(allocator, season_digest);
    defer allocator.free(season);
    const combo = try escapeJsonString(allocator, combo_digest);
    defer allocator.free(combo);
    const board = try escapeJsonString(allocator, board_fingerprint);
    defer allocator.free(board);
    const seal = try escapeJsonString(allocator, playtest_seal);
    defer allocator.free(seal);
    const rivalry = try escapeJsonString(allocator, rivalry_digest);
    defer allocator.free(rivalry);
    const chain = try escapeJsonString(allocator, match_chain_digest);
    defer allocator.free(chain);
    const crown = try escapeJsonString(allocator, match_crown);
    defer allocator.free(crown);
    return try std.fmt.allocPrint(
        allocator,
        "{{\"layout_digest\":{s},\"season_score_digest\":{s},\"combo_digest\":{s},\"board_fingerprint\":{s},\"playtest_seal\":{s},\"rivalry_digest\":{s},\"match_chain_digest\":{s},\"match_crown\":{s}}}",
        .{ layout, season, combo, board, seal, rivalry, chain, crown },
    );
}

pub fn buildHealthJson() []const u8 {
    return "{\"ok\":true}";
}

pub fn buildErrorJson(allocator: std.mem.Allocator, msg: []const u8) ![]u8 {
    const esc = try escapeJsonString(allocator, msg);
    defer allocator.free(esc);
    return try std.fmt.allocPrint(allocator, "{{\"ok\":false,\"error\":{s}}}", .{esc});
}
