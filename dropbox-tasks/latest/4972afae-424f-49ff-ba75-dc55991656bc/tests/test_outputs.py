import json
import os
import subprocess
import tempfile

import pytest

LADDER_SEED = "20260712"
REFEREE_SRC = "/tests/house/referee.c"
ENTRY = "/app/entry"

BAND_BOARDS = 30
COUPLED_BOARDS = 30
LADDER_BOARDS = 30
LADDER_PERIOD = 40
LADDER_PREPERIOD = 62
LADDER_STRUCTURE = "period-40-preperiod-62"


@pytest.fixture(scope="session")
def ladder():
    assert os.path.exists(REFEREE_SRC), "tournament rig source missing"
    work = tempfile.mkdtemp()
    rig = os.path.join(work, "rig")
    build = subprocess.run(
        ["gcc", "-O2", "-o", rig, REFEREE_SRC],
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr
    run = subprocess.run(
        [rig, ENTRY, LADDER_SEED],
        capture_output=True,
        text=True,
        timeout=700,
    )
    assert run.returncode == 0, run.stderr
    data = json.loads(run.stdout)
    assert len(data["boards"]) == BAND_BOARDS + COUPLED_BOARDS + LADDER_BOARDS
    return data


def tier(data, name):
    return [b for b in data["boards"] if b["tier"] == name]


def test_entry_present():
    """An entrant program is seated at /app/entry."""
    assert os.path.isfile(ENTRY), "no entrant at /app/entry"
    assert os.access(ENTRY, os.X_OK), "/app/entry is not executable"


def test_practice_band_matches(ladder):
    """Every practice-band alley is called right and bowled out against the house."""
    boards = tier(ladder, "band")
    assert len(boards) == BAND_BOARDS
    bad = [b for b in boards if not b["call_ok"] or not b["won"]]
    assert not bad, "lost or miscalled %d of %d practice-band alleys: %s" % (
        len(bad),
        BAND_BOARDS,
        bad[:3],
    )


def test_coupled_boards(ladder):
    """Every two-lane alley off the dial's home face is called right and won."""
    boards = tier(ladder, "coupled")
    assert len(boards) == COUPLED_BOARDS
    bad = [b for b in boards if not b["call_ok"] or not b["won"]]
    assert not bad, "lost or miscalled %d of %d coupled alleys: %s" % (
        len(bad),
        COUPLED_BOARDS,
        bad[:3],
    )


def test_ladder_full(ladder):
    """Every tournament-scale alley is called right and won against the house."""
    boards = tier(ladder, "ladder")
    assert len(boards) == LADDER_BOARDS
    assert ladder["period"] == LADDER_PERIOD, (
        "tournament rig mis-derived the alley period"
    )
    assert ladder["preperiod"] == LADDER_PREPERIOD, (
        "tournament rig mis-derived the alley preperiod"
    )
    shape = "period-%d-preperiod-%d" % (ladder["period"], ladder["preperiod"])
    assert shape == LADDER_STRUCTURE, (
        "tournament rig mis-derived the alley structure: %s" % shape
    )
    bad = [b for b in boards if not b["call_ok"] or not b["won"]]
    assert not bad, "lost or miscalled %d of %d tournament alleys: %s" % (
        len(bad),
        LADDER_BOARDS,
        bad[:3],
    )


def test_no_fouls(ladder):
    """The rig never refuses a throw the entrant sends."""
    fouls = [b for b in ladder["boards"] if b["foul"]]
    assert not fouls, "the rig refused a throw on %d alleys: %s" % (
        len(fouls),
        fouls[:3],
    )


def test_concede_discipline(ladder):
    """Winnable alleys are called and unwinnable alleys are conceded."""
    wrong = [b for b in ladder["boards"] if b["call"] != b["truth"]]
    assert not wrong, "called %d alleys wrong: %s" % (len(wrong), wrong[:5])
