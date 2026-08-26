const std = @import("std");
const types = @import("types.zig");
const tapeload = @import("tapeload.zig");
const scorefold = @import("scorefold.zig");
const combostreak = @import("combostreak.zig");
const rivalry = @import("rivalry.zig");
const boardtopo = @import("boardtopo.zig");
const boardprint = @import("boardprint.zig");
const playtestseal = @import("playtestseal.zig");
const chainlatch = @import("chainlatch.zig");
const matchcrown = @import("matchcrown.zig");
const scorecardbuild = @import("scorecardbuild.zig");
const scorecardjson = @import("scorecardjson.zig");

fn applyComboPoints(players: []types.PlayerScore, combo: combostreak.ComboResult) void {
    for (players) |*p| {
        p.combo_points = 0;
        for (combo.players) |c| {
            if (std.mem.eql(u8, c.player_id, p.player_id)) {
                p.combo_points = c.combo_points;
                break;
            }
        }
    }
}

fn applyRivalryPoints(players: []types.PlayerScore, riv: rivalry.RivalryResult) void {
    for (players) |*p| {
        p.rivalry_points = 0;
        for (riv.players) |r| {
            if (std.mem.eql(u8, r.player_id, p.player_id)) {
                p.rivalry_points = r.rivalry_points;
                break;
            }
        }
    }
}

pub fn evaluateArchive(allocator: std.mem.Allocator, archive_path: []const u8) ![]u8 {
    var archive = try tapeload.loadArchive(allocator, archive_path);
    defer archive.deinit();

    const score = try scorefold.foldScores(allocator, &archive);
    defer scorefold.freeScoreResult(allocator, score);

    const combo = try combostreak.foldCombo(allocator, &archive);
    defer combostreak.freeComboResult(allocator, combo);
    applyComboPoints(score.players, combo);

    const riv = try rivalry.foldRivalry(allocator, &archive);
    defer rivalry.freeRivalryResult(allocator, riv);
    applyRivalryPoints(score.players, riv);

    const topo = try boardtopo.buildTopologyDigest(allocator, &archive);
    defer boardtopo.freeTopoResult(allocator, topo);

    const board_fp = try boardprint.boardFingerprint(allocator, &archive);
    defer allocator.free(board_fp);

    const seal = try playtestseal.computePlaytestSeal(
        allocator,
        score.season_score_digest,
        topo.layout_digest,
        combo.combo_digest,
        board_fp,
    );
    defer allocator.free(seal);

    const prior = try chainlatch.readPriorTip(allocator);
    defer allocator.free(prior);
    const chain = try chainlatch.advanceChainLatch(allocator, prior, seal, riv.rivalry_digest);
    defer allocator.free(chain);

    const crown = try matchcrown.computeMatchCrown(allocator, seal, riv.rivalry_digest, chain);
    defer allocator.free(crown);

    const report = try scorecardbuild.assembleReport(
        allocator,
        &archive,
        score.players,
        topo.layout_digest,
        score.season_score_digest,
        topo.topology_dot_path,
        combo.combo_digest,
        board_fp,
        seal,
        riv.rivalry_digest,
        chain,
        crown,
    );
    defer scorecardbuild.freeReport(allocator, &report);

    return scorecardbuild.reportToJson(allocator, report);
}

pub fn digestOnly(allocator: std.mem.Allocator, archive_path: []const u8) ![]u8 {
    var archive = try tapeload.loadArchive(allocator, archive_path);
    defer archive.deinit();
    const score = try scorefold.foldScores(allocator, &archive);
    defer scorefold.freeScoreResult(allocator, score);
    const combo = try combostreak.foldCombo(allocator, &archive);
    defer combostreak.freeComboResult(allocator, combo);
    const riv = try rivalry.foldRivalry(allocator, &archive);
    defer rivalry.freeRivalryResult(allocator, riv);
    const topo = try boardtopo.buildTopologyDigest(allocator, &archive);
    defer boardtopo.freeTopoResult(allocator, topo);
    const board_fp = try boardprint.boardFingerprint(allocator, &archive);
    defer allocator.free(board_fp);
    const seal = try playtestseal.computePlaytestSeal(
        allocator,
        score.season_score_digest,
        topo.layout_digest,
        combo.combo_digest,
        board_fp,
    );
    defer allocator.free(seal);
    const prior = try chainlatch.readPriorTip(allocator);
    defer allocator.free(prior);
    const chain = try chainlatch.advanceChainLatch(allocator, prior, seal, riv.rivalry_digest);
    defer allocator.free(chain);
    const crown = try matchcrown.computeMatchCrown(allocator, seal, riv.rivalry_digest, chain);
    defer allocator.free(crown);
    return scorecardjson.buildDigestJson(
        allocator,
        topo.layout_digest,
        score.season_score_digest,
        combo.combo_digest,
        board_fp,
        seal,
        riv.rivalry_digest,
        chain,
        crown,
    );
}
