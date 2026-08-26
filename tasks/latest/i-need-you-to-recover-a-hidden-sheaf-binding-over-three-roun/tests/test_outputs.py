"""Verifier for the hidden-binding series with a bounded garbled reply.

Grades the ledger the root keeper publishes to /run/ryebank after every round is resolved. The tally
must finish the whole series and win every round, each with its one-shot bind inside the per-round
name budget. The ledger is written by the root keeper into a directory the unprivileged agent user
can read but not write, so the tally cannot forge a win it did not earn. The ledger never contains
the secret stretches or the hidden garble positions. The verifier runs as root, so it can
independently read the ledger and inspect the keeper's files to re-check the outcome.
"""
import json
import os
import pwd

import pytest

LEDGER = "/run/ryebank/ledger.json"
LEDGER_DIR = "/run/ryebank"
KEEPER_DIR = "/opt/keeper"
KEEPER_SECRET = "/opt/keeper/secret.json"
AGENT_USER = "agent"
EXPECTED_ROUNDS = 3
REQUIRED_WINS = 3


def _load():
    """Read the published ledger, failing closed when it is absent."""
    assert os.path.exists(LEDGER), (
        "no ledger on the shared volume: the keeper never finished the series, so no rounds "
        "were played through to completion"
    )
    with open(LEDGER) as fh:
        return json.load(fh)


def _agent_uid():
    """The unprivileged tally's uid, or None if the account is absent."""
    try:
        return pwd.getpwnam(AGENT_USER).pw_uid
    except KeyError:
        return None


@pytest.fixture(scope="module")
def result():
    """The single published ledger, loaded once for the module."""
    return _load()


def test_series_completed(result):
    """The whole series must be resolved, not abandoned midway."""
    assert result.get("finished") is True, "the series is not complete"
    assert len(result.get("rounds", [])) == EXPECTED_ROUNDS, (
        f"expected {EXPECTED_ROUNDS} resolved rounds"
    )


def test_each_round_is_well_formed(result):
    """Each resolved round records its index, a boolean outcome, and a name count that never
    exceeds the budget, with no duplicate indices."""
    budget = result["budget"]
    seen = set()
    for rnd in result["rounds"]:
        idx = rnd.get("index")
        assert isinstance(idx, int) and 0 <= idx < EXPECTED_ROUNDS, "bad round index"
        assert idx not in seen, "duplicate round index"
        seen.add(idx)
        assert isinstance(rnd.get("won"), bool), "round outcome must be a boolean"
        used = rnd.get("names_used")
        assert isinstance(used, int) and 0 <= used <= budget, (
            f"round {idx} reports {used} names, outside 0..{budget}"
        )


def test_win_graded_only_from_trusted_root_ledger():
    """The outcome is graded solely from the ledger the ROOT keeper publishes, which the tally must
    not be able to forge. The ledger file and its directory must be root-owned and NOT writable by
    the unprivileged agent user, so a win recorded here reflects real play the keeper observed, not
    a file the tally wrote. (Replaces a dead check on the won-round name count: the keeper already
    refuses a name once the budget is spent, so names_used can never exceed the budget and that
    assertion could never fail.)"""
    assert os.path.exists(LEDGER), "the published ledger is missing"
    ledger_st = os.stat(LEDGER)
    dir_st = os.stat(LEDGER_DIR)
    assert ledger_st.st_uid == 0, (
        f"the ledger {LEDGER} is owned by uid {ledger_st.st_uid}, not root: a tally-writable ledger "
        f"could be forged"
    )
    assert dir_st.st_uid == 0, (
        f"the ledger directory {LEDGER_DIR} is owned by uid {dir_st.st_uid}, not root"
    )
    # The directory must not be group/other writable, so only root can create or replace the ledger.
    assert not (dir_st.st_mode & 0o022), (
        f"{LEDGER_DIR} is writable by non-root (mode {oct(dir_st.st_mode)}): the tally could "
        f"replace the ledger and forge a win"
    )
    assert not (ledger_st.st_mode & 0o022), (
        f"{LEDGER} is writable by non-root (mode {oct(ledger_st.st_mode)})"
    )


def test_keeper_files_and_state_stay_root_only():
    """The stated rule 'do not read the keeper's files or its hidden state' must be structurally
    enforced: the keeper's directory and this session's secret stretches must remain root-owned and
    unreadable by the unprivileged agent user, so the tally could not have peeked at the answer
    instead of deducing it. This tests the anti-cheat rule directly rather than trusting it."""
    agent_uid = _agent_uid()
    assert os.path.isdir(KEEPER_DIR), f"the keeper directory {KEEPER_DIR} is missing"
    kdir = os.stat(KEEPER_DIR)
    assert kdir.st_uid == 0, f"{KEEPER_DIR} is not root-owned (uid {kdir.st_uid})"
    # Directory must be inaccessible to group/other: no read, no execute/traverse for the agent.
    assert not (kdir.st_mode & 0o077), (
        f"{KEEPER_DIR} is accessible to non-root (mode {oct(kdir.st_mode)}): the agent could reach "
        f"the keeper's files"
    )
    # This session's secret (the hidden stretches + garble indices) is generated at container start
    # and must be root-only 0400 so the agent can neither read nor alter the keeper's state.
    if os.path.exists(KEEPER_SECRET):
        sec = os.stat(KEEPER_SECRET)
        assert sec.st_uid == 0, f"{KEEPER_SECRET} is not root-owned (uid {sec.st_uid})"
        assert not (sec.st_mode & 0o077), (
            f"{KEEPER_SECRET} is readable/writable by non-root (mode {oct(sec.st_mode)}): the "
            f"answer would be exposed to the tally"
        )
        if agent_uid is not None:
            assert sec.st_uid != agent_uid, "the secret must not be owned by the agent user"


def test_player_wins_every_round(result):
    """The tally must win every round of the series within budget."""
    wins = sum(1 for rnd in result["rounds"] if rnd["won"])
    assert wins >= REQUIRED_WINS, (
        f"won {wins} of {len(result['rounds'])} rounds; need at least {REQUIRED_WINS}"
    )
