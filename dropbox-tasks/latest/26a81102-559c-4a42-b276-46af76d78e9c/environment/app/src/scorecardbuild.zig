const std = @import("std");
const types = @import("types.zig");
const scorecardjson = @import("scorecardjson.zig");

pub fn assembleReport(
    allocator: std.mem.Allocator,
    archive: *const types.Archive,
    players: []types.PlayerScore,
    layout_digest: []const u8,
    season_score_digest: []const u8,
    topology_dot_path: []const u8,
    combo_digest: []const u8,
    board_fingerprint: []const u8,
    playtest_seal: []const u8,
    rivalry_digest: []const u8,
    match_chain_digest: []const u8,
    match_crown: []const u8,
) !types.EvalReport {
    var players_copy = try allocator.alloc(types.PlayerScore, players.len);
    for (players, 0..) |p, i| {
        players_copy[i] = .{
            .player_id = try allocator.dupe(u8, p.player_id),
            .points = p.points,
            .moves = p.moves,
            .combo_points = p.combo_points,
            .rivalry_points = p.rivalry_points,
        };
    }
    return types.EvalReport{
        .archive = try allocator.dupe(u8, archive.root),
        .cell_count = archive.cells.items.len,
        .move_count = archive.moves.items.len,
        .players = players_copy,
        .layout_digest = try allocator.dupe(u8, layout_digest),
        .season_score_digest = try allocator.dupe(u8, season_score_digest),
        .topology_dot_path = try allocator.dupe(u8, topology_dot_path),
        .combo_digest = try allocator.dupe(u8, combo_digest),
        .board_fingerprint = try allocator.dupe(u8, board_fingerprint),
        .playtest_seal = try allocator.dupe(u8, playtest_seal),
        .rivalry_digest = try allocator.dupe(u8, rivalry_digest),
        .match_chain_digest = try allocator.dupe(u8, match_chain_digest),
        .match_crown = try allocator.dupe(u8, match_crown),
    };
}

pub fn reportToJson(allocator: std.mem.Allocator, report: types.EvalReport) ![]u8 {
    return scorecardjson.buildReportJson(allocator, report);
}

pub fn freeReport(allocator: std.mem.Allocator, report: *const types.EvalReport) void {
    allocator.free(report.archive);
    for (report.players) |p| allocator.free(p.player_id);
    allocator.free(report.players);
    allocator.free(report.layout_digest);
    allocator.free(report.season_score_digest);
    allocator.free(report.topology_dot_path);
    allocator.free(report.combo_digest);
    allocator.free(report.board_fingerprint);
    allocator.free(report.playtest_seal);
    allocator.free(report.rivalry_digest);
    allocator.free(report.match_chain_digest);
    allocator.free(report.match_crown);
}
