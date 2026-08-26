CipherGrid Season 4 puzzle-league match scoring

Each move tape row names a player_id, cell_id, and tick. The archive cells.json supplies grid topology and the published solution glyph per cell. glyphs.toml maps glyph ids to weight and family strings.

Per-move base points: glyph_weight plus two times the count of orthogonally adjacent cells whose solution glyph shares the same family as the played cell glyph. Round that base to two decimals half-away-from-zero. Glyph pressure multiplies the rounded base by (1.0 + 0.05 * R) where R is how many same-family solution cells have not yet appeared among earlier tape rows (indices strictly before the current move). Round the pressure-adjusted value again to two decimals before summing into player totals. Round each player total the same way.

Combo streaks: for each player, sort that player's moves by tick ascending then cell_id ascending. Walk in order and maintain a family streak. When consecutive moves share a solution glyph family, increase the streak and add 0.25 * (streak_len - 1) to the combo raw total. When families differ, reset streak length to 1. combo_points is the rounded raw total; max_streak is the longest streak seen. combo_digest is SHA-256 hex over newline-joined lines sorted by player_id: player_id|combo_points|max_streak with combo_points at two fractional digits.

Rivalry: for every unordered pair of tape moves from different players whose ticks differ by at most one, whose cells are orthogonal neighbors, and whose solution glyphs share a family, add 0.5 to each player's rivalry raw total. rivalry_points are rounded to two decimals. rivalry_digest is SHA-256 hex over newline-joined lines sorted by player_id: player_id|rivalry_points.

season_score_digest is SHA-256 hex over newline-joined canonical lines sorted by player_id ascending: player_id|total_points|move_count with total_points formatted to exactly two fractional digits.

board_fingerprint is SHA-256 hex over newline-joined lines sorted by cell_id: cell_id|glyph_id|family|degree where degree is the neighbor count from cells.json.

Board map: directed digraph named ciphergrid with one node per cell id. For every undirected adjacency, add a solid edge from lexicographically smaller cell id to larger. For every adjacency where both solution glyphs share a family, add a dashed edge using the same orientation rule. For every adjacency that shares a family and where both cell ids appear somewhere on the move tape, add a dotted echo edge with the same orientation. layout_digest is SHA-256 hex over newline-joined lines sorted by node name: name|x|y from Graphviz plain-layout node placements, each coordinate rounded to two decimals half-away-from-zero.

playtest_seal is SHA-256 hex of the single UTF-8 string season_score_digest|layout_digest|combo_digest|board_fingerprint.

Match chain: read the prior tip from /app/var/match_chain_tip.txt (treat a missing file as empty prior). match_chain_digest is SHA-256 hex of prior|playtest_seal|rivalry_digest. After a successful score, rewrite the tip file to that digest. match_crown is SHA-256 hex of playtest_seal|rivalry_digest|match_chain_digest.
