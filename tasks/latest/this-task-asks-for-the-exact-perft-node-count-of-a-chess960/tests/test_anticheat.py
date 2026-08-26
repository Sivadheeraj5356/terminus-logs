import glob
import os

import reference

APP = "/app"

FORBIDDEN_KEYWORDS = [
    "stockfish",
    "python-chess",
    "pychess",
    "leela",
    "fairy-stockfish",
    "fairystockfish",
    "gaviota",
    "syzygy",
    "polyglot.bin",
    "chessgamelib",
]


def _agent_cpp_sources():
    return sorted(glob.glob(os.path.join(APP, "src", "**", "*.cpp"), recursive=True))


def _strip_comments(text):
    out = []
    i = 0
    n = len(text)
    while i < n:
        if text[i : i + 2] == "//":
            while i < n and text[i] != "\n":
                i += 1
        elif text[i : i + 2] == "/*":
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def test_no_forbidden_engine_keyword_in_source():
    """Verify agent C++ sources contain no forbidden chess-engine or tablebase keywords."""
    for path in _agent_cpp_sources():
        with open(path, errors="ignore") as handle:
            text = _strip_comments(handle.read()).lower()
        for keyword in FORBIDDEN_KEYWORDS:
            assert keyword not in text, "forbidden keyword %r found in %s" % (
                keyword,
                path,
            )


def test_no_hardcoded_hidden_perft_answer_in_source():
    """Verify agent sources do not hardcode any held-back fixture's exact perft integer."""
    for case_name in reference.hidden_case_names():
        path = reference.hidden_case_path(case_name)
        fen, depth = reference.read_position_file(path)
        answer = reference.perft_from_fen(fen, depth, buggy=False)
        needle = str(answer)
        for path2 in _agent_cpp_sources():
            with open(path2, errors="ignore") as handle:
                text = _strip_comments(handle.read())
            assert needle not in text, "hardcoded hidden answer %s found in %s" % (
                needle,
                path2,
            )


def test_castling_module_was_actually_implemented():
    """Verify gen_castle_moves in movegen.cpp is not left as an empty stub."""
    movegen_path = os.path.join(APP, "src", "movegen.cpp")
    with open(movegen_path) as handle:
        text = handle.read()
    assert "gen_castle_moves" in text
    stub_marker = "std::vector<Move> gen_castle_moves(const Position &pos, char side, int king_from) {\n    return {};\n}"
    assert stub_marker not in text.replace("\r\n", "\n")


def test_no_hidden_fixture_names_leaked_into_app():
    """Verify no file under /app references held-back hidden fixture names or paths."""
    hidden_names = reference.hidden_case_names()
    target_prefix = os.path.join(APP, "build") + os.sep
    for path in glob.glob(os.path.join(APP, "**", "*"), recursive=True):
        if not os.path.isfile(path):
            continue
        if path.startswith(target_prefix):
            continue
        with open(path, errors="ignore") as handle:
            text = handle.read()
        assert "/tests/fixtures/hidden" not in text, path
        for name in hidden_names:
            assert name not in text, "%s references hidden fixture name in %s" % (
                name,
                path,
            )


def test_makefile_still_produces_the_expected_binary_path():
    """Verify the Makefile still targets build/chess960_perft as its output binary."""
    with open(os.path.join(APP, "Makefile")) as handle:
        text = handle.read()
    assert "chess960_perft" in text
