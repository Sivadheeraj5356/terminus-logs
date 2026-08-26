"""
Graded integration tests for the Imperial Tribunal Arbitration game.

The binary (tribunal-game) must read scoring values, win thresholds, and
precedent parameters from codex.txt, which overrides the values in sessions.json.
Tests exercise all three scenarios and the precedent mechanic of TRIBUNAL-1605.
"""

import os
import subprocess

BINARY   = "/workspace/tribunal-game"
CODEX    = "/opt/task_data/codex.txt"
SESSIONS = "/opt/task_data/sessions.json"


def run_game(seed, moves):
    """Run the binary with the given move list fed via stdin; return CompletedProcess."""
    text = "\n".join(moves) + "\n"
    return subprocess.run(
        [BINARY, "--codex", CODEX, "--sessions", SESSIONS, "--seed", seed],
        input=text,
        capture_output=True,
        text=True,
        timeout=15,
    )


def out(seed, moves):
    """Return stdout for the given seed and moves."""
    return run_game(seed, moves).stdout


# ---------------------------------------------------------------------------
# Binary existence
# ---------------------------------------------------------------------------

class TestBinaryExists:
    def test_binary_is_executable(self):
        """Binary at /workspace/tribunal-game must exist and be executable."""
        assert os.path.isfile(BINARY) and os.access(BINARY, os.X_OK), \
            f"{BINARY} not found or not executable"


# ---------------------------------------------------------------------------
# File-loading exit codes
# ---------------------------------------------------------------------------

class TestMissingFiles:
    def test_missing_codex_exits_2(self):
        """Missing codex file must produce exit code 2."""
        r = subprocess.run(
            [BINARY, "--codex", "/nonexistent/codex.txt",
             "--sessions", SESSIONS, "--seed", "COURT-1348"],
            capture_output=True, text=True, timeout=10,
        )
        assert r.returncode == 2, \
            f"Expected exit 2 for missing codex, got {r.returncode}"

    def test_missing_sessions_exits_2(self):
        """Missing sessions file must produce exit code 2."""
        r = subprocess.run(
            [BINARY, "--codex", CODEX,
             "--sessions", "/nonexistent/sessions.json", "--seed", "COURT-1348"],
            capture_output=True, text=True, timeout=10,
        )
        assert r.returncode == 2, \
            f"Expected exit 2 for missing sessions, got {r.returncode}"


# ---------------------------------------------------------------------------
# Invalid seed
# ---------------------------------------------------------------------------

class TestInvalidSeed:
    def test_unknown_seed_exits_1(self):
        """An unrecognised seed must produce exit code 1."""
        r = run_game("UNKNOWN-9999", ["adjourn"])
        assert r.returncode == 1, \
            f"Expected exit 1 for unknown seed, got {r.returncode}"

    def test_empty_seed_exits_nonzero(self):
        """An empty seed argument must produce a non-zero exit code."""
        r = subprocess.run(
            [BINARY, "--codex", CODEX, "--sessions", SESSIONS, "--seed", ""],
            input="adjourn\n", capture_output=True, text=True, timeout=10,
        )
        assert r.returncode != 0


# ---------------------------------------------------------------------------
# COURT-1348 — header and basic output format
# ---------------------------------------------------------------------------

class TestCourt1348Header:
    def test_header_contains_session_title(self):
        """Header line must include the session title from sessions.json."""
        o = out("COURT-1348", ["adjourn"])
        assert "Court of the Black Seal, 1348" in o

    def test_header_contains_tribunal_prefix(self):
        """Header line must start with IMPERIAL TRIBUNAL."""
        o = out("COURT-1348", ["adjourn"])
        assert "IMPERIAL TRIBUNAL" in o

    def test_header_shows_open_case_count(self):
        """Header must show 'Open cases: 4' for COURT-1348."""
        o = out("COURT-1348", ["adjourn"])
        assert "Open cases: 4" in o


# ---------------------------------------------------------------------------
# COURT-1348 — cite score from codex (8, not JSON value 10)
# ---------------------------------------------------------------------------

class TestCourt1348CiteScore:
    def test_invoke_merit_is_8_not_10(self):
        """Citation merit must be 8 (codex) not 10 (sessions.json)."""
        o = out("COURT-1348", ["invoke I", "adjourn"])
        assert "Merit: +8" in o, \
            f"Expected cite merit +8 from codex; got:\n{o}"

    def test_invoke_score_after_single_cite(self):
        """Running score after one citation must be 8."""
        o = out("COURT-1348", ["invoke I", "adjourn"])
        assert "Score: 8" in o

    def test_invoke_wrong_json_value_absent(self):
        """Citation must not report the sessions.json value of +10."""
        o = out("COURT-1348", ["invoke I", "adjourn"])
        assert "Merit: +10" not in o


# ---------------------------------------------------------------------------
# COURT-1348 — case grant scores from codex
# ---------------------------------------------------------------------------

class TestCourt1348GrantScores:
    def test_case_a_grant_merit_is_15_not_20(self):
        """CASE-1348-A grant must award 15 (codex) not 20 (sessions.json)."""
        o = out("COURT-1348", ["grant CASE-1348-A", "adjourn"])
        assert "Merit: +15" in o, \
            f"Expected grant merit +15 from codex; got:\n{o}"

    def test_case_c_grant_merit_is_9_not_12(self):
        """CASE-1348-C grant must award 9 (codex) not 12 (sessions.json)."""
        o = out("COURT-1348", ["grant CASE-1348-C", "adjourn"])
        assert "Merit: +9" in o

    def test_case_d_grant_merit_is_14_not_18(self):
        """CASE-1348-D grant must award 14 (codex) not 18 (sessions.json)."""
        o = out("COURT-1348", ["grant CASE-1348-D", "adjourn"])
        assert "Merit: +14" in o

    def test_case_b_grant_merit_is_8(self):
        """CASE-1348-B grant must award 8 (same in codex and sessions.json)."""
        o = out("COURT-1348", ["grant CASE-1348-B", "adjourn"])
        assert "Merit: +8" in o


# ---------------------------------------------------------------------------
# COURT-1348 — win threshold from codex (45, not JSON value 50)
# ---------------------------------------------------------------------------

class TestCourt1348Threshold:
    def test_threshold_line_shows_45_not_50(self):
        """Adjourn must report threshold 45 from codex, not 50 from sessions.json."""
        o = out("COURT-1348", ["adjourn"])
        assert "Threshold: 45." in o, \
            f"Expected threshold 45 from codex; got:\n{o}"

    def test_score_46_is_honoured(self):
        """Score 46 exceeds codex threshold 45 and must yield HONOURED."""
        # invoke(8) + A(15) + C(9) + D(14) = 46
        o = out("COURT-1348", [
            "invoke I", "grant CASE-1348-A",
            "grant CASE-1348-C", "grant CASE-1348-D", "adjourn"
        ])
        assert "VERDICT: HONOURED" in o

    def test_score_46_beats_codex_not_json_threshold(self):
        """Score 46 must be HONOURED (above codex 45) even though it is below JSON 50."""
        o = out("COURT-1348", [
            "invoke I", "grant CASE-1348-A",
            "grant CASE-1348-C", "grant CASE-1348-D", "adjourn"
        ])
        assert "Merit total: 46." in o
        assert "VERDICT: HONOURED" in o

    def test_score_29_is_dishonoured(self):
        """Score 29 must yield DISHONOURED (below codex threshold 45)."""
        # A(15) + D(14) = 29
        o = out("COURT-1348", ["grant CASE-1348-A", "grant CASE-1348-D", "adjourn"])
        assert "VERDICT: DISHONOURED" in o

    def test_all_four_grants_honoured(self):
        """Granting all four cases produces a score above 45 and yields HONOURED."""
        # A(15)+B(8)+C(9)+D(14) = 46
        o = out("COURT-1348", [
            "grant CASE-1348-A", "grant CASE-1348-B",
            "grant CASE-1348-C", "grant CASE-1348-D", "adjourn"
        ])
        assert "VERDICT: HONOURED" in o


# ---------------------------------------------------------------------------
# COURT-1348 — invalid moves
# ---------------------------------------------------------------------------

class TestCourt1348InvalidMoves:
    def test_unknown_case_deducts_penalty(self):
        """Granting an unknown case ID deducts the invalid penalty."""
        o = out("COURT-1348", ["grant CASE-XXXX-Z", "adjourn"])
        assert "[INVALID]" in o
        assert "Case not found" in o

    def test_resolved_case_is_invalid(self):
        """Granting an already-resolved case deducts the invalid penalty."""
        o = out("COURT-1348", ["grant CASE-1348-A", "grant CASE-1348-A", "adjourn"])
        assert "already resolved" in o

    def test_invalid_section_shows_correct_tag(self):
        """Invoking a non-existent section shows [INVALID SECTION]."""
        o = out("COURT-1348", ["invoke IX", "adjourn"])
        assert "[INVALID SECTION]" in o

    def test_deny_unknown_case_deducts_penalty(self):
        """Denying an unknown case ID deducts the invalid penalty."""
        o = out("COURT-1348", ["deny CASE-XXXX-Z", "adjourn"])
        assert "[INVALID]" in o


# ---------------------------------------------------------------------------
# COURT-1348 — deny moves
# ---------------------------------------------------------------------------

class TestCourt1348DenyMoves:
    def test_deny_case_b_earns_positive_score(self):
        """Denying CASE-1348-B earns a positive deny score of 3."""
        o = out("COURT-1348", ["deny CASE-1348-B", "adjourn"])
        assert "Merit: +3" in o

    def test_deny_case_a_earns_negative_score(self):
        """Denying CASE-1348-A deducts 8 merit points."""
        o = out("COURT-1348", ["deny CASE-1348-A", "adjourn"])
        assert "Merit: -8" in o


# ---------------------------------------------------------------------------
# COURT-1348 — status command
# ---------------------------------------------------------------------------

class TestStatusCommand:
    def test_status_shows_score(self):
        """Status command must report the current score."""
        o = out("COURT-1348", ["grant CASE-1348-A", "status", "adjourn"])
        assert "Score: 15" in o

    def test_status_shows_open_cases(self):
        """Status must list cases not yet resolved."""
        o = out("COURT-1348", ["grant CASE-1348-A", "status", "adjourn"])
        assert "Open cases: 3" in o

    def test_status_shows_resolved_cases(self):
        """Status must list resolved cases with their verdict."""
        o = out("COURT-1348", ["grant CASE-1348-A", "status", "adjourn"])
        assert "[GRANTED]" in o
        assert "CASE-1348-A" in o

    def test_status_mid_game_correct_counts(self):
        """After two grants, status must show 2 open and 2 resolved."""
        o = out("COURT-1348", [
            "grant CASE-1348-A", "grant CASE-1348-B", "status", "adjourn"
        ])
        assert "Open cases: 2" in o
        assert "Resolved cases: 2" in o


# ---------------------------------------------------------------------------
# TRIBUNAL-1605 — cite score from codex (10, not JSON value 12)
# ---------------------------------------------------------------------------

class TestTribunal1605CiteScore:
    def test_cite_merit_is_10_not_12(self):
        """Citation merit for TRIBUNAL-1605 must be 10 (codex) not 12 (JSON)."""
        o = out("TRIBUNAL-1605", ["invoke I", "adjourn"])
        assert "Merit: +10" in o

    def test_cite_score_cumulative(self):
        """Two citations must accumulate to score 20."""
        o = out("TRIBUNAL-1605", ["invoke I", "invoke II", "adjourn"])
        lines = [ln for ln in o.splitlines() if "Score:" in ln and "[CITE]" in ln]
        assert len(lines) >= 2
        assert "Score: 20" in lines[1]


# ---------------------------------------------------------------------------
# TRIBUNAL-1605 — precedent mechanic
# ---------------------------------------------------------------------------

class TestTribunal1605Precedent:
    def test_invoke_section_III_activates_precedent(self):
        """Invoking Section III must show PRECEDENT ACTIVE."""
        o = out("TRIBUNAL-1605", ["invoke III", "adjourn"])
        assert "PRECEDENT ACTIVE" in o

    def test_precedent_window_is_3_not_4(self):
        """Precedent window from codex must be 3 grants, not 4 (JSON value)."""
        o = out("TRIBUNAL-1605", ["invoke III", "adjourn"])
        assert "PRECEDENT ACTIVE (3 grants)" in o, \
            f"Expected window of 3 from codex; got:\n{o}"

    def test_json_precedent_window_absent(self):
        """Sessions.json value of 4 grants must NOT appear in precedent message."""
        o = out("TRIBUNAL-1605", ["invoke III", "adjourn"])
        assert "PRECEDENT ACTIVE (4 grants)" not in o

    def test_grant_under_precedent_shows_bonus(self):
        """First grant after invoke III must show the precedent bonus."""
        o = out("TRIBUNAL-1605", ["invoke III", "grant CASE-1605-A", "adjourn"])
        assert "precedent" in o.lower()
        assert "+7 precedent" in o

    def test_precedent_bonus_is_7_not_10(self):
        """Precedent bonus per grant must be 7 (codex) not 10 (sessions.json)."""
        o = out("TRIBUNAL-1605", ["invoke III", "grant CASE-1605-A", "adjourn"])
        assert "+7 precedent" in o, \
            f"Expected bonus of 7 from codex; got:\n{o}"

    def test_third_grant_under_precedent_shows_expired(self):
        """Third grant under precedent must show PRECEDENT EXPIRED."""
        o = out("TRIBUNAL-1605", [
            "invoke III",
            "grant CASE-1605-A",
            "grant CASE-1605-B",
            "grant CASE-1605-C",
            "adjourn",
        ])
        assert "PRECEDENT EXPIRED" in o

    def test_fourth_grant_has_no_precedent_bonus(self):
        """Fourth grant after invoke III must have no precedent bonus (window is 3)."""
        o = out("TRIBUNAL-1605", [
            "invoke III",
            "grant CASE-1605-A",
            "grant CASE-1605-B",
            "grant CASE-1605-C",
            "grant CASE-1605-D",
            "adjourn",
        ])
        lines = o.splitlines()
        d_lines = [ln for ln in lines if "CASE-1605-D" in ln]
        assert d_lines, "No output line found for CASE-1605-D"
        d_line = d_lines[0]
        assert "precedent" not in d_line.lower(), \
            f"CASE-1605-D (4th grant) must not carry precedent bonus; got: {d_line}"

    def test_fourth_grant_merit_is_base_only(self):
        """Fourth grant (CASE-1605-D) must show merit +18, no bonus."""
        o = out("TRIBUNAL-1605", [
            "invoke III",
            "grant CASE-1605-A",
            "grant CASE-1605-B",
            "grant CASE-1605-C",
            "grant CASE-1605-D",
            "adjourn",
        ])
        d_lines = [ln for ln in o.splitlines() if "CASE-1605-D" in ln]
        assert d_lines
        assert "Merit: +18" in d_lines[0], \
            f"Expected Merit: +18 for CASE-1605-D without bonus; got: {d_lines[0]}"


# ---------------------------------------------------------------------------
# TRIBUNAL-1605 — win threshold (62, not JSON value 70)
# ---------------------------------------------------------------------------

class TestTribunal1605Victory:
    def test_threshold_is_62_not_70(self):
        """Threshold for TRIBUNAL-1605 must be 62 (codex) not 70 (JSON)."""
        o = out("TRIBUNAL-1605", ["adjourn"])
        assert "Threshold: 62." in o

    def test_all_grants_without_precedent_is_dishonoured(self):
        """Granting all five cases without precedent scores 59, below threshold 62."""
        # A(12)+B(11)+C(10)+D(18)+E(8) = 59 < 62
        o = out("TRIBUNAL-1605", [
            "grant CASE-1605-A", "grant CASE-1605-B", "grant CASE-1605-C",
            "grant CASE-1605-D", "grant CASE-1605-E", "adjourn",
        ])
        assert "Merit total: 59." in o
        assert "VERDICT: DISHONOURED" in o

    def test_victory_with_precedent(self):
        """Invoke III + grant A/B/C (all with precedent) + grant D yields HONOURED."""
        # invoke(10)+A(12+7)+B(11+7)+C(10+7)+D(18) = 10+19+18+17+18 = 82
        o = out("TRIBUNAL-1605", [
            "invoke III",
            "grant CASE-1605-A",
            "grant CASE-1605-B",
            "grant CASE-1605-C",
            "grant CASE-1605-D",
            "adjourn",
        ])
        assert "VERDICT: HONOURED" in o

    def test_cite_plus_all_grants_honoured(self):
        """One citation + all five grants is enough to cross threshold 62."""
        # invoke(10)+59 = 69 >= 62
        o = out("TRIBUNAL-1605", [
            "invoke II",
            "grant CASE-1605-A", "grant CASE-1605-B", "grant CASE-1605-C",
            "grant CASE-1605-D", "grant CASE-1605-E", "adjourn",
        ])
        assert "VERDICT: HONOURED" in o

    def test_case_d_grant_score_from_codex(self):
        """CASE-1605-D grant must award 18 (codex) not 22 (sessions.json)."""
        o = out("TRIBUNAL-1605", ["grant CASE-1605-D", "adjourn"])
        assert "Merit: +18" in o


# ---------------------------------------------------------------------------
# ASSEMBLY-1789 — cite score (11, not JSON value 14)
# ---------------------------------------------------------------------------

class TestAssembly1789CiteScore:
    def test_cite_merit_is_11_not_14(self):
        """Citation merit for ASSEMBLY-1789 must be 11 (codex) not 14 (JSON)."""
        o = out("ASSEMBLY-1789", ["invoke I", "adjourn"])
        assert "Merit: +11" in o

    def test_cite_score_wrong_json_value_absent(self):
        """Citation must not report sessions.json value of +14."""
        o = out("ASSEMBLY-1789", ["invoke I", "adjourn"])
        assert "Merit: +14" not in o


# ---------------------------------------------------------------------------
# ASSEMBLY-1789 — invalid section penalty (12, not JSON value 8)
# ---------------------------------------------------------------------------

class TestAssembly1789InvalidPenalty:
    def test_invalid_section_deducts_12_not_8(self):
        """Invalid section invocation in ASSEMBLY-1789 must deduct 12 (codex) not 8 (JSON)."""
        o = out("ASSEMBLY-1789", ["invoke VIII", "adjourn"])
        assert "Merit: -12" in o, \
            f"Expected penalty -12 from codex; got:\n{o}"

    def test_invalid_section_penalty_wrong_json_value_absent(self):
        """Invalid section penalty must not be the sessions.json value of -8."""
        o = out("ASSEMBLY-1789", ["invoke VIII", "adjourn"])
        assert "Merit: -8" not in o

    def test_score_after_invalid_invoke(self):
        """Score after one invalid invoke must be -12."""
        o = out("ASSEMBLY-1789", ["invoke VIII", "adjourn"])
        assert "Score: -12" in o


# ---------------------------------------------------------------------------
# ASSEMBLY-1789 — win threshold (80, not JSON value 90)
# ---------------------------------------------------------------------------

class TestAssembly1789Victory:
    def test_threshold_is_80_not_90(self):
        """Threshold for ASSEMBLY-1789 must be 80 (codex) not 90 (JSON)."""
        o = out("ASSEMBLY-1789", ["adjourn"])
        assert "Threshold: 80." in o

    def test_all_six_grants_honoured(self):
        """Granting all six cases gives 82 points and must yield HONOURED."""
        # A(14)+B(16)+C(10)+D(11)+E(13)+F(18) = 82
        o = out("ASSEMBLY-1789", [
            "grant CASE-1789-A", "grant CASE-1789-B", "grant CASE-1789-C",
            "grant CASE-1789-D", "grant CASE-1789-E", "grant CASE-1789-F",
            "adjourn",
        ])
        assert "Merit total: 82." in o
        assert "VERDICT: HONOURED" in o

    def test_five_grants_plus_cite_honoured_beats_codex_not_json_threshold(self):
        """Score 83 must be HONOURED (above codex 80) even though it is below JSON 90."""
        # A(14)+B(16)+D(11)+E(13)+F(18)+invoke(11) = 83
        o = out("ASSEMBLY-1789", [
            "grant CASE-1789-A", "grant CASE-1789-B",
            "grant CASE-1789-D", "grant CASE-1789-E", "grant CASE-1789-F",
            "invoke I", "adjourn",
        ])
        assert "Merit total: 83." in o
        assert "VERDICT: HONOURED" in o, \
            f"Score 83 must be HONOURED against codex threshold 80; got:\n{o}"

    def test_five_grants_without_cite_dishonoured(self):
        """Five grants without citation scores 72, below threshold 80 — DISHONOURED."""
        # A(14)+B(16)+D(11)+E(13)+F(18) = 72
        o = out("ASSEMBLY-1789", [
            "grant CASE-1789-A", "grant CASE-1789-B",
            "grant CASE-1789-D", "grant CASE-1789-E", "grant CASE-1789-F",
            "adjourn",
        ])
        assert "VERDICT: DISHONOURED" in o

    def test_case_a_grant_merit_from_codex(self):
        """CASE-1789-A grant must award 14 (codex) not 18 (sessions.json)."""
        o = out("ASSEMBLY-1789", ["grant CASE-1789-A", "adjourn"])
        assert "Merit: +14" in o

    def test_case_b_grant_merit_from_codex(self):
        """CASE-1789-B grant must award 16 (codex) not 20 (sessions.json)."""
        o = out("ASSEMBLY-1789", ["grant CASE-1789-B", "adjourn"])
        assert "Merit: +16" in o

    def test_case_f_grant_merit_from_codex(self):
        """CASE-1789-F grant must award 18 (codex) not 22 (sessions.json)."""
        o = out("ASSEMBLY-1789", ["grant CASE-1789-F", "adjourn"])
        assert "Merit: +18" in o


# ---------------------------------------------------------------------------
# Output format consistency
# ---------------------------------------------------------------------------

class TestOutputFormat:
    def test_granted_line_has_correct_tag(self):
        """A successful grant must produce a line beginning with [GRANTED]."""
        o = out("COURT-1348", ["grant CASE-1348-A", "adjourn"])
        assert any(ln.startswith("[GRANTED]") for ln in o.splitlines())

    def test_cite_line_has_correct_tag(self):
        """A valid invocation must produce a line beginning with [CITE]."""
        o = out("COURT-1348", ["invoke I", "adjourn"])
        assert any(ln.startswith("[CITE]") for ln in o.splitlines())

    def test_adjourn_prints_session_adjourned(self):
        """Adjourn must print SESSION ADJOURNED on its own line."""
        o = out("COURT-1348", ["adjourn"])
        assert "SESSION ADJOURNED" in o

    def test_adjourn_prints_verdict_line(self):
        """Adjourn must print a line starting with VERDICT:."""
        o = out("COURT-1348", ["adjourn"])
        assert any(ln.startswith("VERDICT:") for ln in o.splitlines())

    def test_adjourn_prints_merit_total_line(self):
        """Adjourn must print a line containing 'Merit total:'."""
        o = out("COURT-1348", ["adjourn"])
        assert "Merit total:" in o

    def test_denied_positive_shows_plus_sign(self):
        """A positive deny score (CASE-1348-B) must display Merit: +N."""
        o = out("COURT-1348", ["deny CASE-1348-B", "adjourn"])
        lines = [ln for ln in o.splitlines() if "[DENIED]" in ln]
        assert lines and "Merit: +3" in lines[0]

    def test_game_is_deterministic(self):
        """Identical move sequences must produce identical output."""
        moves = ["invoke I", "grant CASE-1348-A", "adjourn"]
        assert out("COURT-1348", moves) == out("COURT-1348", moves)


# ---------------------------------------------------------------------------
# COURT-1348 — deny scores for all four cases (from codex)
# ---------------------------------------------------------------------------

class TestCourt1348AllDenyScores:
    def test_deny_case_c_deducts_5(self):
        """Denying CASE-1348-C deducts 5 merit points (codex value)."""
        o = out("COURT-1348", ["deny CASE-1348-C", "adjourn"])
        assert "Merit: -5" in o, f"Expected Merit: -5 for deny C; got:\n{o}"

    def test_deny_case_d_deducts_4(self):
        """Denying CASE-1348-D deducts 4 merit points (codex value)."""
        o = out("COURT-1348", ["deny CASE-1348-D", "adjourn"])
        assert "Merit: -4" in o, f"Expected Merit: -4 for deny D; got:\n{o}"

    def test_deny_case_b_score_after_deny(self):
        """After denying CASE-1348-B, running score must be 3."""
        o = out("COURT-1348", ["deny CASE-1348-B", "status", "adjourn"])
        assert "Score: 3" in o

    def test_deny_case_c_score_after_deny(self):
        """After denying CASE-1348-C, running score must be -5."""
        o = out("COURT-1348", ["deny CASE-1348-C", "status", "adjourn"])
        assert "Score: -5" in o

    def test_cite_plus_deny_c_cumulative_score(self):
        """cite(+8) then deny C(-5) must yield cumulative score 3."""
        o = out("COURT-1348", ["invoke I", "deny CASE-1348-C", "adjourn"])
        lines = [ln for ln in o.splitlines() if "CASE-1348-C" in ln]
        assert lines and "Score: 3" in lines[0]


# ---------------------------------------------------------------------------
# TRIBUNAL-1605 — precedent re-invocation behaviour
# ---------------------------------------------------------------------------

class TestTribunal1605PrecedentReinvoke:
    def test_reinvoke_section_iii_after_expiry_resets_counter(self):
        """Re-invoking Section III after Precedent expires restarts it with 3 grants."""
        o = out("TRIBUNAL-1605", [
            "invoke III",
            "grant CASE-1605-A",
            "grant CASE-1605-B",
            "grant CASE-1605-C",  # Precedent expires here
            "invoke III",         # fresh Precedent
            "adjourn",
        ])
        # The second invoke III line must show PRECEDENT ACTIVE (3 grants)
        lines = o.splitlines()
        invoke_lines = [ln for ln in lines if "[CITE] Section III" in ln]
        assert len(invoke_lines) >= 2, "Expected two Section III citation lines"
        assert "PRECEDENT ACTIVE (3 grants)" in invoke_lines[1], (
            f"Second invoke III must restart with 3 grants; got: {invoke_lines[1]}"
        )

    def test_grant_after_reinvoke_earns_precedent_bonus(self):
        """Grant issued after re-invocation of Section III earns the precedent bonus."""
        o = out("TRIBUNAL-1605", [
            "invoke III",
            "grant CASE-1605-A",
            "grant CASE-1605-B",
            "grant CASE-1605-C",  # expires
            "invoke III",         # restart
            "grant CASE-1605-D",  # must earn +7
            "adjourn",
        ])
        d_lines = [ln for ln in o.splitlines() if "CASE-1605-D" in ln]
        assert d_lines, "No output for CASE-1605-D"
        assert "+7 precedent" in d_lines[0], (
            f"CASE-1605-D after re-invoke must earn +7 precedent bonus; got: {d_lines[0]}"
        )

    def test_reinvoke_during_active_precedent_resets_counter(self):
        """Invoking Section III while Precedent is still active resets the window to 3."""
        o = out("TRIBUNAL-1605", [
            "invoke III",
            "grant CASE-1605-A",  # 2 remaining
            "invoke III",         # reset to 3
            "grant CASE-1605-B",  # 2 remaining under fresh precedent
            "adjourn",
        ])
        lines = o.splitlines()
        invoke_lines = [ln for ln in lines if "[CITE] Section III" in ln]
        assert len(invoke_lines) >= 2
        # After re-invoke during active precedent, counter resets to 3
        assert "PRECEDENT ACTIVE (3 grants)" in invoke_lines[1], (
            f"Mid-window re-invoke must reset to 3 grants; got: {invoke_lines[1]}"
        )


# ---------------------------------------------------------------------------
# ASSEMBLY-1789 — deny scores for all six cases
# ---------------------------------------------------------------------------

class TestAssembly1789DenyScores:
    def test_deny_case_c_awards_positive(self):
        """Denying CASE-1789-C awards 2 merit points (positive deny)."""
        o = out("ASSEMBLY-1789", ["deny CASE-1789-C", "adjourn"])
        assert "Merit: +2" in o, f"Expected Merit: +2 for deny C; got:\n{o}"

    def test_deny_case_e_deducts_8(self):
        """Denying CASE-1789-E deducts 8 merit points."""
        o = out("ASSEMBLY-1789", ["deny CASE-1789-E", "adjourn"])
        assert "Merit: -8" in o, f"Expected Merit: -8 for deny E; got:\n{o}"

    def test_deny_case_f_deducts_12(self):
        """Denying CASE-1789-F deducts 12 merit points (codex value, not sessions.json)."""
        o = out("ASSEMBLY-1789", ["deny CASE-1789-F", "adjourn"])
        assert "Merit: -12" in o, f"Expected Merit: -12 for deny F; got:\n{o}"

    def test_deny_case_d_deducts_6(self):
        """Denying CASE-1789-D deducts 6 merit points."""
        o = out("ASSEMBLY-1789", ["deny CASE-1789-D", "adjourn"])
        assert "Merit: -6" in o, f"Expected Merit: -6 for deny D; got:\n{o}"

    def test_mixed_deny_grant_score_tracking(self):
        """Score accumulates correctly across mixed grants and denials."""
        # deny C(+2) + grant A(14) + deny D(-6) = 10
        o = out("ASSEMBLY-1789", [
            "deny CASE-1789-C",
            "grant CASE-1789-A",
            "deny CASE-1789-D",
            "adjourn",
        ])
        assert "Merit total: 10." in o, f"Expected Merit total: 10.; got:\n{o}"
