"""CipherGrid puzzle-league verifier: CLI scores and Graphviz board map."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import cipher_ref
import pytest
from conftest import (
    CHAIN_TIP,
    CIPHERLEAGUE,
    SCHEMA_PATH,
    STOCK_ARCHIVE,
    clear_chain_tip,
    ref_evaluate,
    run_cli,
    run_evaluate,
    run_evaluate_fresh,
)


def _clone_archive(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


class TestMilestone1:
    """CipherGrid season-4 puzzle-league scoring and Graphviz board-map checks."""

    def test_binary_exists(self):
        """cipherleague must be installed at the documented path."""
        assert Path(CIPHERLEAGUE).is_file()

    def test_schema_lists_agent_modules(self):
        """Schema contract must name combo, rivalry, and echo match-bonus surfaces."""
        schema = json.loads(SCHEMA_PATH.read_text())
        mods = schema["implementation"]["modules"]
        assert mods == [
            "combostreak.zig",
            "rivalry.zig",
            "echoedge.zig",
        ]
        provided = schema["implementation"]["provided"]
        assert "tapeload.zig" in provided
        assert "boardprint.zig" in provided
        assert "playtestseal.zig" in provided
        assert "boardtopo.zig" in provided
        assert "matchplay.zig" in provided
        assert "familyadj.zig" in provided
        assert "edgerule.zig" in provided
        assert "scorefold.zig" in provided
        assert "movepoints.zig" in provided
        assert "glyphpressure.zig" in provided
        assert "chainlatch.zig" in provided
        assert "matchcrown.zig" in provided

    def test_evaluate_writes_report_file(self, tmp_path):
        """CLI score must create the requested match scorecard on disk."""
        out = tmp_path / "report.json"
        run_evaluate(STOCK_ARCHIVE, out)
        assert out.is_file()

    def test_report_archive_path(self, stock_report):
        """Scorecard echoes the scored archive absolute path."""
        assert stock_report["archive"] == str(STOCK_ARCHIVE)

    def test_report_cell_count(self, stock_report, ref_stock):
        """Cell count matches the stock cells.json grid size."""
        assert stock_report["cell_count"] == ref_stock["cell_count"] == 9

    def test_report_move_count(self, stock_report, ref_stock):
        """Move count matches stock moves.jsonl row count."""
        assert stock_report["move_count"] == ref_stock["move_count"] == 6

    def test_report_players_sorted(self, stock_report):
        """Players array is sorted by player_id ascending."""
        ids = [p["player_id"] for p in stock_report["players"]]
        assert ids == sorted(ids)

    def test_report_player_points_match_reference(self, stock_report, ref_stock):
        """Each player total matches the independent Python scorer."""
        by_id = {p["player_id"]: p for p in stock_report["players"]}
        for ref_p in ref_stock["players"]:
            assert by_id[ref_p["player_id"]]["points"] == pytest.approx(
                ref_p["points"], abs=1e-9
            )

    def test_report_player_move_counts(self, stock_report, ref_stock):
        """Per-player move counts match the reference fold."""
        by_id = {p["player_id"]: p for p in stock_report["players"]}
        for ref_p in ref_stock["players"]:
            assert by_id[ref_p["player_id"]]["moves"] == ref_p["moves"]

    def test_season_score_digest_matches_reference(self, stock_report, ref_stock):
        """season_score_digest must equal the canonical reference hash."""
        assert stock_report["season_score_digest"] == ref_stock["season_score_digest"]

    def test_layout_digest_matches_reference(self, stock_report, ref_stock):
        """layout_digest must equal dot plain layout reference hash."""
        assert stock_report["layout_digest"] == ref_stock["layout_digest"]

    def test_topology_dot_file_written(self, stock_report):
        """Scoring must materialize the Graphviz digraph under /app/var."""
        dot_path = Path(stock_report["topology_dot_path"])
        assert dot_path.is_file()
        text = dot_path.read_text()
        assert "digraph ciphergrid" in text

    def test_dot_contains_solid_adjacency_edge(self, stock_report):
        """Solid adjacency edges use lexicographic orientation."""
        text = Path(stock_report["topology_dot_path"]).read_text()
        assert '"c00" -> "c01";' in text

    def test_dot_contains_dashed_family_edge(self, stock_report):
        """Same-family adjacency adds dashed glyph edges."""
        text = Path(stock_report["topology_dot_path"]).read_text()
        assert "[style=dashed]" in text

    def test_points_are_two_decimal_floats(self, stock_report):
        """Reported player points are representable at two decimals."""
        for player in stock_report["players"]:
            pts = player["points"]
            assert abs(pts - round(pts, 2)) < 1e-9

    def test_evaluate_is_deterministic(self, tmp_path):
        """Repeated genesis score runs on stock data must be identical."""
        out1 = tmp_path / "a.json"
        out2 = tmp_path / "b.json"
        first = run_evaluate_fresh(STOCK_ARCHIVE, out1)
        second = run_evaluate_fresh(STOCK_ARCHIVE, out2)
        assert first == second

    def test_evaluate_missing_archive_fails(self, tmp_path):
        """Unknown archive path must exit non-zero."""
        out = tmp_path / "bad.json"
        proc = run_cli("score", "--archive", "/app/data/missing", "--out", str(out))
        assert proc.returncode != 0

    def test_nova_total_points_reference(self, stock_report, ref_stock):
        """Nova season total matches reference scoring."""
        nova = next(p for p in stock_report["players"] if p["player_id"] == "nova")
        ref = next(p for p in ref_stock["players"] if p["player_id"] == "nova")
        assert nova["points"] == pytest.approx(ref["points"], abs=1e-9)

    def test_echo_total_points_reference(self, stock_report, ref_stock):
        """Echo season total matches reference scoring."""
        echo = next(p for p in stock_report["players"] if p["player_id"] == "echo")
        ref = next(p for p in ref_stock["players"] if p["player_id"] == "echo")
        assert echo["points"] == pytest.approx(ref["points"], abs=1e-9)

    def test_reference_move_point_c00(self):
        """c00 base is weight plus twice luminous neighbors; index-0 pressure scales it."""
        archive = cipher_ref.load_archive(STOCK_ARCHIVE)
        assert cipher_ref.base_move_points(archive, "c00") == 7.0
        assert cipher_ref.move_points(archive, "c00", 0) == pytest.approx(
            9.45, abs=1e-9
        )

    def test_reference_move_point_c11(self):
        """Star hub base counts celestial neighbors; pressure uses remaining celestial cells."""
        archive = cipher_ref.load_archive(STOCK_ARCHIVE)
        assert cipher_ref.base_move_points(archive, "c11") == 8.0
        assert cipher_ref.move_points(archive, "c11", 0) == pytest.approx(
            8.80, abs=1e-9
        )

    def test_reference_season_lines_sorted(self, ref_stock):
        """Canonical season lines sort by player_id before hashing."""
        archive = cipher_ref.load_archive(STOCK_ARCHIVE)
        _, digest = cipher_ref.fold_scores(archive)
        assert digest == ref_stock["season_score_digest"]

    def test_layout_nodes_sorted_by_name(self, ref_stock):
        """Layout digest sorts dot node names before hashing coordinates."""
        archive = cipher_ref.load_archive(STOCK_ARCHIVE)
        layout, _ = cipher_ref.topology_digest(archive)
        assert layout == ref_stock["layout_digest"]

    def test_scorecard_mentions_half_away_rounding(self):
        """Published scorecard documents half-away-from-zero rounding."""
        text = (STOCK_ARCHIVE / "scorecard.md").read_text()
        assert "half-away-from-zero" in text

    def test_glyphs_toml_has_three_glyphs(self):
        """Stock glyph table defines sun, moon, and star entries."""
        archive = cipher_ref.load_archive(STOCK_ARCHIVE)
        assert set(archive.glyphs) == {"sun", "moon", "star"}

    def test_solution_covers_all_cells(self):
        """Every grid cell has a solution glyph assignment."""
        archive = cipher_ref.load_archive(STOCK_ARCHIVE)
        for cell in archive.cells:
            assert cell.cell_id in archive.solution

    def test_moves_reference_tick_order(self):
        """Stock tape includes six ticks across two players."""
        archive = cipher_ref.load_archive(STOCK_ARCHIVE)
        ticks = sorted(m.tick for m in archive.moves)
        assert ticks == [1, 1, 2, 2, 3, 3]

    def test_report_topology_path_under_var(self, stock_report):
        """topology_dot_path must live under /app/var."""
        assert stock_report["topology_dot_path"].startswith("/app/var/")

    def test_score_player_count(self, stock_report):
        """Stock match scorecard lists both league players."""
        assert len(stock_report["players"]) == 2

    def test_repeated_score_seals_agree(self, tmp_path):
        """Two score runs on a mutated archive keep playtest seals; chain tip advances."""
        archive_dir = tmp_path / "twice"
        _clone_archive(STOCK_ARCHIVE, archive_dir)
        lines = (archive_dir / "moves.jsonl").read_text().splitlines()
        row = json.loads(lines[-1])
        row["player_id"] = "echo"
        lines[-1] = json.dumps(row)
        (archive_dir / "moves.jsonl").write_text("\n".join(lines) + "\n")
        first = run_evaluate_fresh(archive_dir, tmp_path / "a.json")
        second = run_evaluate(archive_dir, tmp_path / "b.json")
        assert first["playtest_seal"] == second["playtest_seal"]
        assert first["combo_digest"] == second["combo_digest"]
        assert first["board_fingerprint"] == second["board_fingerprint"]
        assert first["match_chain_digest"] != second["match_chain_digest"]
        ref = ref_evaluate(archive_dir, prior_tip="")
        assert first["season_score_digest"] == ref["season_score_digest"]
        assert first["layout_digest"] == ref["layout_digest"]
        assert first["combo_digest"] == ref["combo_digest"]
        assert first["board_fingerprint"] == ref["board_fingerprint"]
        assert first["playtest_seal"] == ref["playtest_seal"]

    def test_cli_stdout_silent_on_success(self, tmp_path):
        """Successful score should not print report to stdout."""
        out = tmp_path / "quiet.json"
        proc = run_cli("score", "--archive", str(STOCK_ARCHIVE), "--out", str(out))
        assert proc.returncode == 0
        assert proc.stdout.strip() == ""

    def test_dot_has_nine_nodes(self, stock_report):
        """Topology digraph includes one node per cell."""
        text = Path(stock_report["topology_dot_path"]).read_text()
        for cid in (
            [f"c0{i}" for i in range(3)]
            + [f"c1{i}" for i in range(3)]
            + [f"c2{i}" for i in range(3)]
        ):
            assert f'"{cid}";' in text

    def test_family_edge_orientation_lexicographic(self, stock_report):
        """Dashed family edges never reverse lexicographic order."""
        text = Path(stock_report["topology_dot_path"]).read_text()
        for line in text.splitlines():
            if "style=dashed" not in line:
                continue
            parts = line.strip().split("->")
            left = parts[0].strip().strip('"')
            right = parts[1].split("[")[0].strip().strip('"')
            assert left < right

    def test_dynamic_bypass_check(self, tmp_path):
        """Mutating a move tape row must change season_score_digest."""
        archive_dir = tmp_path / "mutated"
        _clone_archive(STOCK_ARCHIVE, archive_dir)
        lines = (archive_dir / "moves.jsonl").read_text().splitlines()
        row = json.loads(lines[0])
        row["cell_id"] = "c22"
        lines[0] = json.dumps(row)
        (archive_dir / "moves.jsonl").write_text("\n".join(lines) + "\n")

        out = tmp_path / "mut.json"
        mutated = run_evaluate(archive_dir, out)
        stock = ref_evaluate(STOCK_ARCHIVE)
        assert mutated["season_score_digest"] != stock["season_score_digest"]
        ref_mut = ref_evaluate(archive_dir)
        assert mutated["season_score_digest"] == ref_mut["season_score_digest"]

    def test_dynamic_extra_move_changes_digest(self, tmp_path):
        """Appending a move row changes both move_count and digest."""
        archive_dir = tmp_path / "extra"
        _clone_archive(STOCK_ARCHIVE, archive_dir)
        with (archive_dir / "moves.jsonl").open("a") as fh:
            fh.write(
                json.dumps({"player_id": "nova", "cell_id": "c20", "tick": 4}) + "\n"
            )
        out = tmp_path / "extra.json"
        report = run_evaluate(archive_dir, out)
        assert report["move_count"] == 7
        ref = ref_evaluate(archive_dir)
        assert report["season_score_digest"] == ref["season_score_digest"]

    def test_dynamic_glyph_weight_shift(self, tmp_path):
        """Editing glyph weight in glyphs.toml shifts player totals."""
        archive_dir = tmp_path / "heavy"
        _clone_archive(STOCK_ARCHIVE, archive_dir)
        text = (archive_dir / "glyphs.toml").read_text()
        text = text.replace("weight = 3.0", "weight = 5.0", 1)
        (archive_dir / "glyphs.toml").write_text(text)
        out = tmp_path / "heavy.json"
        report = run_evaluate(archive_dir, out)
        ref = ref_evaluate(archive_dir)
        assert report["players"][0]["points"] == pytest.approx(
            ref["players"][0]["points"], abs=1e-9
        )
        stock = ref_evaluate(STOCK_ARCHIVE)
        assert report["season_score_digest"] != stock["season_score_digest"]

    def test_dynamic_layout_digest_stable_when_only_moves_change(self, tmp_path):
        """Reassigning players on the same cell set must keep layout_digest stable."""
        archive_dir = tmp_path / "moves_only"
        _clone_archive(STOCK_ARCHIVE, archive_dir)
        lines = (archive_dir / "moves.jsonl").read_text().splitlines()
        row = json.loads(lines[-1])
        row["player_id"] = "echo" if row["player_id"] == "nova" else "nova"
        lines[-1] = json.dumps(row)
        (archive_dir / "moves.jsonl").write_text("\n".join(lines) + "\n")
        out = tmp_path / "layout.json"
        report = run_evaluate_fresh(archive_dir, out)
        stock = ref_evaluate(STOCK_ARCHIVE)
        assert report["layout_digest"] == stock["layout_digest"]
        assert report["season_score_digest"] != stock["season_score_digest"]

    def test_report_json_fields_complete(self, stock_report):
        """Report includes every schema-required top-level field."""
        required = {
            "archive",
            "cell_count",
            "move_count",
            "players",
            "layout_digest",
            "season_score_digest",
            "topology_dot_path",
            "combo_digest",
            "board_fingerprint",
            "playtest_seal",
            "rivalry_digest",
            "match_chain_digest",
            "match_crown",
        }
        assert required.issubset(stock_report.keys())

    def test_player_objects_have_required_keys(self, stock_report):
        """Each player entry exposes id, points, moves, combo_points, and rivalry_points."""
        for player in stock_report["players"]:
            assert {
                "player_id",
                "points",
                "moves",
                "combo_points",
                "rivalry_points",
            } <= set(player.keys())

    def test_stock_combo_digest_matches_reference(self, stock_report, ref_stock):
        """Stock tape combo_digest matches the independent streak fold."""
        assert stock_report["combo_digest"] == ref_stock["combo_digest"]

    def test_stock_board_fingerprint_matches_reference(self, stock_report, ref_stock):
        """board_fingerprint seals solution families and degrees for stock cells."""
        assert stock_report["board_fingerprint"] == ref_stock["board_fingerprint"]

    def test_stock_playtest_seal_matches_reference(self, stock_report, ref_stock):
        """playtest_seal folds season, layout, combo, and board digests."""
        assert stock_report["playtest_seal"] == ref_stock["playtest_seal"]
        expected = cipher_ref.playtest_seal(
            stock_report["season_score_digest"],
            stock_report["layout_digest"],
            stock_report["combo_digest"],
            stock_report["board_fingerprint"],
        )
        assert stock_report["playtest_seal"] == expected

    def test_stock_combo_points_zero_without_streak(self, stock_report):
        """Stock tape has no consecutive same-family plays, so combo_points are zero."""
        for player in stock_report["players"]:
            assert player["combo_points"] == 0.0

    def test_familyadj_neighbor_count_c00(self):
        """c00 luminous neighbors must match shared family_adj counting."""
        archive = cipher_ref.load_archive(STOCK_ARCHIVE)
        assert cipher_ref.neighbor_family_matches(archive, "c00") == 2

    def test_edgerule_family_consistency_with_adj(self, stock_report):
        """Every dashed DOT edge must correspond to a same-family adjacency."""
        archive = cipher_ref.load_archive(STOCK_ARCHIVE)
        text = Path(stock_report["topology_dot_path"]).read_text()
        for line in text.splitlines():
            if "style=dashed" not in line:
                continue
            parts = line.strip().split("->")
            left = parts[0].strip().strip('"')
            right = parts[1].split("[")[0].strip().strip('"')
            assert cipher_ref.cells_share_family(archive, left, right)

    def test_multi_step_evaluate_combo_then_seal(self, tmp_path):
        """Build a luminous streak archive, score, and check combo then seal."""
        archive_dir = tmp_path / "streak"
        _clone_archive(STOCK_ARCHIVE, archive_dir)
        moves = [
            {"player_id": "nova", "cell_id": "c00", "tick": 1},
            {"player_id": "nova", "cell_id": "c01", "tick": 2},
            {"player_id": "nova", "cell_id": "c02", "tick": 3},
            {"player_id": "echo", "cell_id": "c11", "tick": 1},
        ]
        (archive_dir / "moves.jsonl").write_text(
            "\n".join(json.dumps(m) for m in moves) + "\n"
        )
        out = tmp_path / "streak.json"
        report = run_evaluate(archive_dir, out)
        ref = ref_evaluate(archive_dir)
        assert report["combo_digest"] == ref["combo_digest"]
        nova = next(p for p in report["players"] if p["player_id"] == "nova")
        assert nova["combo_points"] == pytest.approx(0.75, abs=1e-9)
        assert report["playtest_seal"] == ref["playtest_seal"]
        assert report["season_score_digest"] == ref["season_score_digest"]

    def test_cross_module_score_and_family_edges(self, tmp_path):
        """Changing a solution family must update points and dashed edge presence together."""
        archive_dir = tmp_path / "flip_family"
        _clone_archive(STOCK_ARCHIVE, archive_dir)
        cells = json.loads((archive_dir / "cells.json").read_text())
        cells["solution"]["c01"] = "star"
        (archive_dir / "cells.json").write_text(json.dumps(cells))
        out = tmp_path / "flip.json"
        report = run_evaluate(archive_dir, out)
        ref = ref_evaluate(archive_dir)
        assert report["season_score_digest"] == ref["season_score_digest"]
        assert report["board_fingerprint"] == ref["board_fingerprint"]
        stock = ref_evaluate(STOCK_ARCHIVE)
        assert report["board_fingerprint"] != stock["board_fingerprint"]
        text = Path(report["topology_dot_path"]).read_text()
        assert '"c00" -> "c01" [style=dashed];' not in text

    def test_dynamic_combo_streak_bonus(self, tmp_path):
        """Randomized same-family move chains must change combo_digest and seal."""
        import random

        rng = random.Random(42)
        archive_dir = tmp_path / "dyn_combo"
        _clone_archive(STOCK_ARCHIVE, archive_dir)
        stock_arch = cipher_ref.load_archive(STOCK_ARCHIVE)
        luminous = [
            cid
            for cid, g in stock_arch.solution.items()
            if stock_arch.glyphs[g].family == "luminous"
        ]
        chosen = rng.sample(luminous, k=3)
        moves = [
            {"player_id": "nova", "cell_id": chosen[0], "tick": 1},
            {"player_id": "nova", "cell_id": chosen[1], "tick": 2},
            {"player_id": "nova", "cell_id": chosen[2], "tick": 3},
        ]
        (archive_dir / "moves.jsonl").write_text(
            "\n".join(json.dumps(m) for m in moves) + "\n"
        )
        report = run_evaluate(archive_dir, tmp_path / "dyn_combo.json")
        ref = ref_evaluate(archive_dir)
        assert report["combo_digest"] == ref["combo_digest"]
        assert report["players"][0]["combo_points"] == pytest.approx(
            ref["players"][0]["combo_points"], abs=1e-9
        )
        assert report["playtest_seal"] == ref["playtest_seal"]
        stock = ref_evaluate(STOCK_ARCHIVE)
        assert report["combo_digest"] != stock["combo_digest"]

    def test_dynamic_board_fingerprint_glyph_swap(self, tmp_path):
        """Swapping distinct solution glyphs must change board_fingerprint and playtest_seal."""
        archive_dir = tmp_path / "swap"
        _clone_archive(STOCK_ARCHIVE, archive_dir)
        cells = json.loads((archive_dir / "cells.json").read_text())
        # sun <-> star (distinct glyphs/families)
        cells["solution"]["c00"], cells["solution"]["c11"] = (
            cells["solution"]["c11"],
            cells["solution"]["c00"],
        )
        (archive_dir / "cells.json").write_text(json.dumps(cells))
        report = run_evaluate(archive_dir, tmp_path / "swap.json")
        ref = ref_evaluate(archive_dir)
        stock = ref_evaluate(STOCK_ARCHIVE)
        assert report["board_fingerprint"] == ref["board_fingerprint"]
        assert report["board_fingerprint"] != stock["board_fingerprint"]
        assert report["playtest_seal"] == ref["playtest_seal"]
        assert report["playtest_seal"] != stock["playtest_seal"]
        # Family-edge set can shift, so layout may change with the solution map.
        assert report["layout_digest"] == ref["layout_digest"]

    def test_dynamic_tick_order_changes_combo(self, tmp_path):
        """Same cells with reversed ticks can change combo when families realign."""
        archive_dir = tmp_path / "ticks"
        _clone_archive(STOCK_ARCHIVE, archive_dir)
        moves = [
            {"player_id": "echo", "cell_id": "c00", "tick": 1},
            {"player_id": "echo", "cell_id": "c11", "tick": 2},
            {"player_id": "echo", "cell_id": "c02", "tick": 3},
        ]
        (archive_dir / "moves.jsonl").write_text(
            "\n".join(json.dumps(m) for m in moves) + "\n"
        )
        report_a = run_evaluate(archive_dir, tmp_path / "a.json")
        moves_b = [
            {"player_id": "echo", "cell_id": "c00", "tick": 1},
            {"player_id": "echo", "cell_id": "c02", "tick": 2},
            {"player_id": "echo", "cell_id": "c11", "tick": 3},
        ]
        (archive_dir / "moves.jsonl").write_text(
            "\n".join(json.dumps(m) for m in moves_b) + "\n"
        )
        report_b = run_evaluate(archive_dir, tmp_path / "b.json")
        assert report_a["combo_digest"] != report_b["combo_digest"]
        ref_b = ref_evaluate(archive_dir)
        assert report_b["combo_digest"] == ref_b["combo_digest"]
        assert report_b["players"][0]["combo_points"] == pytest.approx(0.25, abs=1e-9)

    def test_dynamic_playtest_seal_tracks_layout_change(self, tmp_path):
        """Adding an isolated cell edge changes board degree fingerprint and seal."""
        archive_dir = tmp_path / "deg"
        _clone_archive(STOCK_ARCHIVE, archive_dir)
        cells = json.loads((archive_dir / "cells.json").read_text())
        for cell in cells["cells"]:
            if cell["id"] == "c00" and "c02" not in cell["neighbors"]:
                cell["neighbors"].append("c02")
            if cell["id"] == "c02" and "c00" not in cell["neighbors"]:
                cell["neighbors"].append("c00")
        (archive_dir / "cells.json").write_text(json.dumps(cells))
        report = run_evaluate(archive_dir, tmp_path / "deg.json")
        ref = ref_evaluate(archive_dir)
        stock = ref_evaluate(STOCK_ARCHIVE)
        assert report["board_fingerprint"] == ref["board_fingerprint"]
        assert report["board_fingerprint"] != stock["board_fingerprint"]
        assert report["playtest_seal"] == ref["playtest_seal"]
        assert report["layout_digest"] != stock["layout_digest"]

    def test_edge_single_move_combo_zero(self, tmp_path):
        """A one-move tape must report combo_points 0.00 and max streak one in digest."""
        archive_dir = tmp_path / "single"
        _clone_archive(STOCK_ARCHIVE, archive_dir)
        (archive_dir / "moves.jsonl").write_text(
            json.dumps({"player_id": "nova", "cell_id": "c11", "tick": 1}) + "\n"
        )
        report = run_evaluate(archive_dir, tmp_path / "single.json")
        ref = ref_evaluate(archive_dir)
        assert report["players"][0]["combo_points"] == 0.0
        assert report["combo_digest"] == ref["combo_digest"]
        assert report["playtest_seal"] == ref["playtest_seal"]

    def test_reference_digest_hex_length(self, ref_stock):
        """Season, layout, combo, board, rivalry, chain, crown, and playtest seals are SHA-256 hex."""
        for key in (
            "layout_digest",
            "season_score_digest",
            "combo_digest",
            "board_fingerprint",
            "playtest_seal",
            "rivalry_digest",
            "match_chain_digest",
            "match_crown",
        ):
            val = ref_stock[key]
            assert len(val) == 64
            assert val == val.lower()


class TestPressureRivalryChain:
    """Additive pressure, rivalry, echo-edge, and match-chain crown behaviors."""

    def test_stock_rivalry_digest_matches_reference(self, stock_report, ref_stock):
        """Stock rivalry_digest must match the independent clash fold."""
        assert stock_report["rivalry_digest"] == ref_stock["rivalry_digest"]

    def test_stock_match_crown_matches_reference(self, stock_report, ref_stock):
        """Genesis match_crown folds seal, rivalry, and chain digests."""
        assert stock_report["match_crown"] == ref_stock["match_crown"]
        expected = cipher_ref.match_crown(
            stock_report["playtest_seal"],
            stock_report["rivalry_digest"],
            stock_report["match_chain_digest"],
        )
        assert stock_report["match_crown"] == expected

    def test_stock_chain_tip_file_written(self, tmp_path):
        """Successful score must persist match_chain_tip under /app/var."""
        report = run_evaluate_fresh(STOCK_ARCHIVE, tmp_path / "tip.json")
        assert CHAIN_TIP.is_file()
        assert CHAIN_TIP.read_text().strip() == report["match_chain_digest"]

    def test_dot_contains_dotted_echo_edge(self, stock_report):
        """Tape-covered same-family adjacencies emit dotted echo edges."""
        text = Path(stock_report["topology_dot_path"]).read_text()
        assert "[style=dotted]" in text

    def test_echo_edge_requires_both_cells_on_tape(self, tmp_path):
        """Removing a cell from the tape must drop its dotted echo edges."""
        archive_dir = tmp_path / "no_echo"
        _clone_archive(STOCK_ARCHIVE, archive_dir)
        (archive_dir / "moves.jsonl").write_text(
            json.dumps({"player_id": "nova", "cell_id": "c00", "tick": 1}) + "\n"
        )
        report = run_evaluate_fresh(archive_dir, tmp_path / "no_echo.json")
        text = Path(report["topology_dot_path"]).read_text()
        assert "[style=dotted]" not in text
        assert "[style=dashed]" in text

    def test_pressure_drops_as_family_cells_are_played(self, tmp_path):
        """Later luminous plays must score lower pressure than the first luminous play."""
        archive_dir = tmp_path / "pressure"
        _clone_archive(STOCK_ARCHIVE, archive_dir)
        moves = [
            {"player_id": "nova", "cell_id": "c00", "tick": 1},
            {"player_id": "nova", "cell_id": "c02", "tick": 2},
        ]
        (archive_dir / "moves.jsonl").write_text(
            "\n".join(json.dumps(m) for m in moves) + "\n"
        )
        archive = cipher_ref.load_archive(archive_dir)
        first = cipher_ref.move_points(archive, "c00", 0)
        second = cipher_ref.move_points(archive, "c02", 1)
        assert first > second
        report = run_evaluate_fresh(archive_dir, tmp_path / "pressure.json")
        ref = ref_evaluate(archive_dir)
        assert report["season_score_digest"] == ref["season_score_digest"]
        assert report["players"][0]["points"] == pytest.approx(
            ref["players"][0]["points"], abs=1e-9
        )

    def test_cross_module_pressure_changes_season_and_crown(self, tmp_path):
        """Reordering different-base luminous plays changes season digest and crown."""
        archive_dir = tmp_path / "reorder"
        _clone_archive(STOCK_ARCHIVE, archive_dir)
        moves_a = [
            {"player_id": "nova", "cell_id": "c00", "tick": 1},
            {"player_id": "nova", "cell_id": "c01", "tick": 2},
            {"player_id": "echo", "cell_id": "c11", "tick": 1},
        ]
        (archive_dir / "moves.jsonl").write_text(
            "\n".join(json.dumps(m) for m in moves_a) + "\n"
        )
        report_a = run_evaluate_fresh(archive_dir, tmp_path / "a.json")
        moves_b = [
            {"player_id": "nova", "cell_id": "c01", "tick": 1},
            {"player_id": "nova", "cell_id": "c00", "tick": 2},
            {"player_id": "echo", "cell_id": "c11", "tick": 1},
        ]
        (archive_dir / "moves.jsonl").write_text(
            "\n".join(json.dumps(m) for m in moves_b) + "\n"
        )
        report_b = run_evaluate_fresh(archive_dir, tmp_path / "b.json")
        assert report_a["season_score_digest"] != report_b["season_score_digest"]
        assert report_a["match_crown"] != report_b["match_crown"]
        ref_b = ref_evaluate(archive_dir)
        assert report_b["match_crown"] == ref_b["match_crown"]

    def test_rivalry_awards_adjacent_clash(self, tmp_path):
        """Neighbor same-family plays within one tick must award rivalry to both players."""
        archive_dir = tmp_path / "riv"
        _clone_archive(STOCK_ARCHIVE, archive_dir)
        moves = [
            {"player_id": "nova", "cell_id": "c00", "tick": 1},
            {"player_id": "echo", "cell_id": "c01", "tick": 1},
        ]
        (archive_dir / "moves.jsonl").write_text(
            "\n".join(json.dumps(m) for m in moves) + "\n"
        )
        report = run_evaluate_fresh(archive_dir, tmp_path / "riv.json")
        ref = ref_evaluate(archive_dir)
        by_id = {p["player_id"]: p for p in report["players"]}
        assert by_id["nova"]["rivalry_points"] == pytest.approx(0.5, abs=1e-9)
        assert by_id["echo"]["rivalry_points"] == pytest.approx(0.5, abs=1e-9)
        assert report["rivalry_digest"] == ref["rivalry_digest"]
        assert report["match_crown"] == ref["match_crown"]

    def test_rivalry_absent_when_ticks_too_far(self, tmp_path):
        """Same neighbor clash with tick gap greater than one must yield zero rivalry."""
        archive_dir = tmp_path / "riv_gap"
        _clone_archive(STOCK_ARCHIVE, archive_dir)
        moves = [
            {"player_id": "nova", "cell_id": "c00", "tick": 1},
            {"player_id": "echo", "cell_id": "c01", "tick": 3},
        ]
        (archive_dir / "moves.jsonl").write_text(
            "\n".join(json.dumps(m) for m in moves) + "\n"
        )
        report = run_evaluate_fresh(archive_dir, tmp_path / "gap.json")
        for player in report["players"]:
            assert player["rivalry_points"] == 0.0

    def test_multi_step_chain_advances_tip(self, tmp_path):
        """Three successive scores must advance tip and crown while playtest seal stays fixed."""
        archive_dir = tmp_path / "chain"
        _clone_archive(STOCK_ARCHIVE, archive_dir)
        clear_chain_tip()
        reports = []
        for i in range(3):
            reports.append(run_evaluate(archive_dir, tmp_path / f"c{i}.json"))
        seals = [r["playtest_seal"] for r in reports]
        chains = [r["match_chain_digest"] for r in reports]
        crowns = [r["match_crown"] for r in reports]
        assert seals[0] == seals[1] == seals[2]
        assert len(set(chains)) == 3
        assert len(set(crowns)) == 3
        assert CHAIN_TIP.read_text().strip() == chains[-1]

    def test_interacting_rivalry_and_echo_layout(self, tmp_path):
        """Adding a second tape cell that completes an echo edge must change layout and crown."""
        archive_dir = tmp_path / "echo_riv"
        _clone_archive(STOCK_ARCHIVE, archive_dir)
        (archive_dir / "moves.jsonl").write_text(
            json.dumps({"player_id": "nova", "cell_id": "c00", "tick": 1}) + "\n"
        )
        report_one = run_evaluate_fresh(archive_dir, tmp_path / "one.json")
        moves = [
            {"player_id": "nova", "cell_id": "c00", "tick": 1},
            {"player_id": "echo", "cell_id": "c01", "tick": 1},
        ]
        (archive_dir / "moves.jsonl").write_text(
            "\n".join(json.dumps(m) for m in moves) + "\n"
        )
        report_two = run_evaluate_fresh(archive_dir, tmp_path / "two.json")
        assert report_one["layout_digest"] != report_two["layout_digest"]
        assert "[style=dotted]" in Path(report_two["topology_dot_path"]).read_text()
        assert report_two["rivalry_digest"] != report_one["rivalry_digest"]
        ref = ref_evaluate(archive_dir)
        assert report_two["match_crown"] == ref["match_crown"]

    def test_edge_empty_prior_chain_uses_empty_string(self, tmp_path):
        """Missing tip file must hash an empty prior into match_chain_digest."""
        archive_dir = tmp_path / "genesis"
        _clone_archive(STOCK_ARCHIVE, archive_dir)
        report = run_evaluate_fresh(archive_dir, tmp_path / "g.json")
        expected = cipher_ref.match_chain_digest(
            "", report["playtest_seal"], report["rivalry_digest"]
        )
        assert report["match_chain_digest"] == expected

    def test_dynamic_random_pressure_order(self, tmp_path):
        """Swapping sun/moon play order under pressure must reseal season_score_digest."""
        archive_dir = tmp_path / "dyn_pressure"
        _clone_archive(STOCK_ARCHIVE, archive_dir)
        moves = [
            {"player_id": "nova", "cell_id": "c00", "tick": 1},
            {"player_id": "nova", "cell_id": "c01", "tick": 2},
            {"player_id": "nova", "cell_id": "c02", "tick": 3},
            {"player_id": "nova", "cell_id": "c10", "tick": 4},
        ]
        (archive_dir / "moves.jsonl").write_text(
            "\n".join(json.dumps(m) for m in moves) + "\n"
        )
        report = run_evaluate_fresh(archive_dir, tmp_path / "dp.json")
        ref = ref_evaluate(archive_dir)
        assert report["season_score_digest"] == ref["season_score_digest"]
        assert report["match_crown"] == ref["match_crown"]
        moves2 = [
            {"player_id": "nova", "cell_id": "c01", "tick": 1},
            {"player_id": "nova", "cell_id": "c00", "tick": 2},
            {"player_id": "nova", "cell_id": "c10", "tick": 3},
            {"player_id": "nova", "cell_id": "c02", "tick": 4},
        ]
        (archive_dir / "moves.jsonl").write_text(
            "\n".join(json.dumps(m) for m in moves2) + "\n"
        )
        report2 = run_evaluate_fresh(archive_dir, tmp_path / "dp2.json")
        assert report2["season_score_digest"] != report["season_score_digest"]

    def test_dynamic_random_rivalry_pair(self, tmp_path):
        """Random adjacent luminous clash must award rivalry and reseal rivalry_digest."""
        import random

        rng = random.Random(99)
        archive_dir = tmp_path / "dyn_riv"
        _clone_archive(STOCK_ARCHIVE, archive_dir)
        stock = cipher_ref.load_archive(STOCK_ARCHIVE)
        pairs = []
        for cell in stock.cells:
            fam = cipher_ref.cell_family(stock, cell.cell_id)
            if fam != "luminous":
                continue
            for nb in cell.neighbors:
                if cipher_ref.cell_family(stock, nb) != "luminous":
                    continue
                a, b = sorted([cell.cell_id, nb])
                pairs.append((a, b))
        a, b = rng.choice(sorted(set(pairs)))
        moves = [
            {"player_id": "nova", "cell_id": a, "tick": 2},
            {"player_id": "echo", "cell_id": b, "tick": 1},
        ]
        (archive_dir / "moves.jsonl").write_text(
            "\n".join(json.dumps(m) for m in moves) + "\n"
        )
        report = run_evaluate_fresh(archive_dir, tmp_path / "dr.json")
        ref = ref_evaluate(archive_dir)
        assert report["rivalry_digest"] == ref["rivalry_digest"]
        assert sum(p["rivalry_points"] for p in report["players"]) == pytest.approx(
            1.0, abs=1e-9
        )

    def test_dynamic_random_echo_changes_layout(self, tmp_path):
        """Randomly expanding the tape to cover a dashed pair must change layout_digest."""
        import random

        rng = random.Random(3)
        archive_dir = tmp_path / "dyn_echo"
        _clone_archive(STOCK_ARCHIVE, archive_dir)
        stock = cipher_ref.load_archive(STOCK_ARCHIVE)
        dashed = []
        for cell in stock.cells:
            for nb in cell.neighbors:
                if cipher_ref.cells_share_family(stock, cell.cell_id, nb):
                    edge = tuple(sorted([cell.cell_id, nb]))
                    dashed.append(edge)
        a, b = rng.choice(sorted(set(dashed)))
        (archive_dir / "moves.jsonl").write_text(
            json.dumps({"player_id": "nova", "cell_id": a, "tick": 1}) + "\n"
        )
        one = run_evaluate_fresh(archive_dir, tmp_path / "e1.json")
        moves = [
            {"player_id": "nova", "cell_id": a, "tick": 1},
            {"player_id": "echo", "cell_id": b, "tick": 2},
        ]
        (archive_dir / "moves.jsonl").write_text(
            "\n".join(json.dumps(m) for m in moves) + "\n"
        )
        two = run_evaluate_fresh(archive_dir, tmp_path / "e2.json")
        assert one["layout_digest"] != two["layout_digest"]
        assert two["layout_digest"] == ref_evaluate(archive_dir)["layout_digest"]

    def test_dynamic_random_chain_sequence(self, tmp_path):
        """Randomized successive scores must keep seals fixed while crowns diverge."""
        import random

        rng = random.Random(11)
        archive_dir = tmp_path / "dyn_chain"
        _clone_archive(STOCK_ARCHIVE, archive_dir)
        clear_chain_tip()
        crowns = []
        seals = []
        for i in range(rng.randint(3, 5)):
            report = run_evaluate(archive_dir, tmp_path / f"dc{i}.json")
            crowns.append(report["match_crown"])
            seals.append(report["playtest_seal"])
        assert len(set(seals)) == 1
        assert len(set(crowns)) == len(crowns)

    def test_dynamic_combo_and_pressure_together(self, tmp_path):
        """Same-family streak with pressure order must agree on combo and season digests."""
        import random

        rng = random.Random(21)
        archive_dir = tmp_path / "combo_pressure"
        _clone_archive(STOCK_ARCHIVE, archive_dir)
        stock = cipher_ref.load_archive(STOCK_ARCHIVE)
        luminous = [
            cid
            for cid, g in stock.solution.items()
            if stock.glyphs[g].family == "luminous"
        ]
        chosen = rng.sample(luminous, k=3)
        moves = [
            {"player_id": "nova", "cell_id": chosen[0], "tick": 1},
            {"player_id": "nova", "cell_id": chosen[1], "tick": 2},
            {"player_id": "nova", "cell_id": chosen[2], "tick": 3},
            {"player_id": "echo", "cell_id": "c11", "tick": 1},
        ]
        (archive_dir / "moves.jsonl").write_text(
            "\n".join(json.dumps(m) for m in moves) + "\n"
        )
        report = run_evaluate_fresh(archive_dir, tmp_path / "cp.json")
        ref = ref_evaluate(archive_dir)
        assert report["combo_digest"] == ref["combo_digest"]
        assert report["season_score_digest"] == ref["season_score_digest"]
        assert report["match_crown"] == ref["match_crown"]
        nova = next(p for p in report["players"] if p["player_id"] == "nova")
        assert nova["combo_points"] == pytest.approx(0.75, abs=1e-9)

    def test_scorecard_documents_pressure_and_chain(self):
        """Published scorecard must describe glyph pressure and match-chain tip rules."""
        text = (STOCK_ARCHIVE / "scorecard.md").read_text()
        assert "Glyph pressure" in text or "glyph pressure" in text.lower()
        assert "match_chain" in text or "match chain" in text.lower()
        assert "rivalry" in text.lower()
