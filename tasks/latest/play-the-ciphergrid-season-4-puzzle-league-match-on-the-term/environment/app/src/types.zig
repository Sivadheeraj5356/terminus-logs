const std = @import("std");

pub const Glyph = struct {
    id: []const u8,
    weight: f64,
    family: []const u8,
};

pub const Cell = struct {
    id: []const u8,
    x: i32,
    y: i32,
    neighbors: std.ArrayList([]const u8),
};

pub const Move = struct {
    player_id: []const u8,
    cell_id: []const u8,
    tick: i32,
};

pub const PlayerScore = struct {
    player_id: []const u8,
    points: f64,
    moves: i32,
    combo_points: f64,
    rivalry_points: f64,
};

pub const LayoutNode = struct {
    name: []const u8,
    x: f64,
    y: f64,
};

pub const Archive = struct {
    root: []const u8,
    cells: std.ArrayList(Cell),
    solution: std.StringHashMap([]const u8),
    glyphs: std.StringHashMap(Glyph),
    moves: std.ArrayList(Move),
    allocator: std.mem.Allocator,

    pub fn deinit(self: *Archive) void {
        for (self.cells.items) |*cell| {
            self.allocator.free(cell.id);
            for (cell.neighbors.items) |n| self.allocator.free(n);
            cell.neighbors.deinit();
        }
        self.cells.deinit();
        var sol_it = self.solution.iterator();
        while (sol_it.next()) |entry| {
            self.allocator.free(entry.key_ptr.*);
            self.allocator.free(entry.value_ptr.*);
        }
        self.solution.deinit();
        var gly_it = self.glyphs.iterator();
        while (gly_it.next()) |entry| {
            self.allocator.free(entry.key_ptr.*);
            self.allocator.free(entry.value_ptr.id);
            self.allocator.free(entry.value_ptr.family);
        }
        self.glyphs.deinit();
        for (self.moves.items) |m| {
            self.allocator.free(m.player_id);
            self.allocator.free(m.cell_id);
        }
        self.moves.deinit();
        self.allocator.free(self.root);
    }
};

pub const EvalReport = struct {
    archive: []const u8,
    cell_count: usize,
    move_count: usize,
    players: []PlayerScore,
    layout_digest: []const u8,
    season_score_digest: []const u8,
    topology_dot_path: []const u8,
    combo_digest: []const u8,
    board_fingerprint: []const u8,
    playtest_seal: []const u8,
    rivalry_digest: []const u8,
    match_chain_digest: []const u8,
    match_crown: []const u8,
};

pub const PendingError = error{
    Pending,
};

pub const ArchiveError = error{
    FileNotFound,
    InvalidArchive,
    MissingGlyph,
    UnknownCell,
};

pub fn roundHalfAwayFromZero(value: f64) f64 {
    if (value >= 0.0) {
        return @floor(value * 100.0 + 0.5) / 100.0;
    }
    return @ceil(value * 100.0 - 0.5) / 100.0;
}

pub fn formatFixed2(allocator: std.mem.Allocator, value: f64) ![]u8 {
    const rounded = roundHalfAwayFromZero(value);
    return try std.fmt.allocPrint(allocator, "{d:.2}", .{rounded});
}

pub fn dupe(allocator: std.mem.Allocator, s: []const u8) ![]u8 {
    return try allocator.dupe(u8, s);
}

pub const VAR_DIR = "/app/var";
pub const DEFAULT_ARCHIVE = "/app/data/season4";
