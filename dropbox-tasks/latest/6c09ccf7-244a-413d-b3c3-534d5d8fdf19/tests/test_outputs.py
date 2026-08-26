"""Verification for the Aldreth county deeds registry host.

Every check reads final runtime state and asserts against what the standing
orders and the county minute, read whole, require, not against the drifted
state the registry was found in.
"""
import os

from conftest import (
    CHARGES,
    CHARGES_IN_FORCE,
    CLERKS,
    DEEDS,
    GROUND,
    REGISTER,
    REGISTRAR,
    SEAL,
    SPENT_COPY_SEED,
    STRUCK_DEPUTY,
    group_members,
    mode_of,
    owner_of,
    sha256_of,
)


class TestCharges:
    """Part 2: the register of charges holds the enrolments of the charges in
    force and nothing besides, no enrolment of a charge put an end to and no
    matter that is not an enrolment of a charge in force."""

    def test_the_register_holds_exactly_the_charges_in_force(self):
        """The charges register holds exactly the enrolments of the charges in force."""
        have = set(os.listdir(CHARGES))
        assert have == CHARGES_IN_FORCE, \
            "the register of charges does not hold exactly the charges in force: %s" % sorted(have)


class TestSpentCopy:
    """Part 2: no copy of a charge put an end to survives anywhere under the
    registry, among the deeds no less than elsewhere, by its content."""

    def test_no_copy_of_a_spent_charge_survives_anywhere(self):
        """No copy carrying the matter of a satisfied or vacated charge survives
        anywhere under the registry ground, whatever leaf it is filed under."""
        spent = sha256_of(SPENT_COPY_SEED) if os.path.exists(SPENT_COPY_SEED) else None
        offenders = []
        for root_dir, _dirs, files in os.walk(GROUND):
            for name in files:
                p = os.path.join(root_dir, name)
                try:
                    if spent is not None and sha256_of(p) == spent:
                        offenders.append(p)
                except OSError:
                    continue
        assert not offenders, \
            "a copy of a charge put an end to still stands in the registry: %s" % offenders


class TestSeal:
    """Part 4: the registrar's seal is held to the registrar's reading alone.
    The registrar reads the seal to set the mark and reads it only, so it is
    held at the strictest keeping that still lets it read, owner-read-only."""

    def test_the_seal_is_held_under_the_registrar(self):
        """The seal is owned by the registrar account."""
        owner, _ = owner_of(SEAL)
        assert owner == REGISTRAR, "the seal is not held by the registrar: %s" % owner

    def test_the_seal_is_held_to_the_reading_alone(self):
        """The seal is held owner-read-only, mode 0400, the registrar reading it
        to seal and writing it by no hand, and no other account reaching it."""
        assert mode_of(SEAL) == 0o400, \
            "the seal is not held at the strictest keeping the orders give, read " \
            "by the registrar and written by no hand: mode %o" % mode_of(SEAL)


class TestRegister:
    """Part 3: the register of titles is a made record, kept to the registry."""

    def test_the_register_is_held_under_the_registry(self):
        """The register of titles is owned by the registrar and the clerks group."""
        owner, group = owner_of(REGISTER)
        assert owner == REGISTRAR, "the register is not the registrar's: %s" % owner
        assert group == CLERKS, "the register is not the registry's: %s" % group

    def test_the_register_is_closed_to_the_wider_host(self):
        """The register admits no account beyond the registry."""
        assert (mode_of(REGISTER) & 0o007) == 0, \
            "the register lies open to the wider host: mode %o" % mode_of(REGISTER)


class TestDeeds:
    """Part 5: the enrolled deeds stand as they are lodged, but for the spent
    copy the orders reach; the muniment room is not emptied."""

    def test_the_muniment_room_keeps_its_enrolled_deeds(self):
        """The muniment room still holds its body of enrolled deeds."""
        deeds = [n for n in os.listdir(DEEDS) if n.endswith(".deed")]
        kept = [n for n in deeds if sha256_of(os.path.join(DEEDS, n)) != _spent_digest()]
        assert len(kept) >= 200, \
            "the muniment room has lost its enrolled deeds: %d kept" % len(kept)


class TestGround:
    """Part 5: the registry ground is the county's own, closed to the wider host."""

    def test_the_ground_is_held_under_the_registry(self):
        """The registry ground is owned by the registrar and the clerks group."""
        owner, group = owner_of(GROUND)
        assert owner == REGISTRAR, "the ground is not the registrar's: %s" % owner
        assert group == CLERKS, "the ground is not the registry's: %s" % group

    def test_the_ground_is_closed_to_the_wider_host(self):
        """The registry ground admits no account beyond the registry."""
        assert (mode_of(GROUND) & 0o007) == 0, \
            "the registry ground lies open to the wider host: mode %o" % mode_of(GROUND)


class TestStruckDeputy:
    """Part 5: the deputy is put off the registry in full, the account kept."""

    def test_the_deputy_is_barred_from_entry(self):
        """The struck deputy's account is barred by shell and locked password."""
        import pwd as _pwd
        shell = _pwd.getpwnam(STRUCK_DEPUTY).pw_shell
        assert shell in ("/usr/sbin/nologin", "/sbin/nologin", "/bin/false"), \
            "the struck deputy keeps a login shell: %s" % shell
        with open("/etc/shadow") as fh:
            for line in fh:
                parts = line.split(":")
                if parts and parts[0] == STRUCK_DEPUTY:
                    pw = parts[1]
                    assert pw.startswith("!") or pw.startswith("*") or pw == "", \
                        "the struck deputy's password is not locked"
                    break

    def test_the_deputy_admission_is_taken_up(self):
        """The struck deputy keeps no admission key."""
        import pwd as _pwd
        home = _pwd.getpwnam(STRUCK_DEPUTY).pw_dir
        ak = os.path.join(home, ".ssh", "authorized_keys")
        if os.path.isfile(ak):
            with open(ak) as fh:
                body = "".join(
                    ln for ln in fh if ln.strip() and not ln.strip().startswith("#")
                )
            assert body.strip() == "", \
                "the struck deputy still keeps an admission key"

    def test_the_deputy_account_is_kept(self):
        """The struck deputy's account is kept on the host as a record."""
        import pwd as _pwd
        try:
            _pwd.getpwnam(STRUCK_DEPUTY)
        except KeyError:
            raise AssertionError("the struck deputy's account was deleted, not kept")


class TestServingHands:
    """Part 5: the serving clerks keep their places."""

    def test_the_serving_clerks_remain_enrolled(self):
        """The serving clerks remain in the registry company."""
        members = group_members(CLERKS)
        for c in ("tolman", "bazeley"):
            assert c in members, "a serving clerk was lost from the registry: %s" % c


class TestRecords:
    """The registry's posted papers stand as written."""

    def test_the_posted_papers_stand_as_written(self):
        """The standing orders, the minute, and the reference are unaltered."""
        for digest, path in _protected_pairs():
            assert os.path.isfile(path), "a posted paper is missing: %s" % path
            assert sha256_of(path) == digest, \
                "a posted paper of the registry has been altered: %s" % path


def _spent_digest():
    return sha256_of(SPENT_COPY_SEED) if os.path.exists(SPENT_COPY_SEED) else ""


def _protected_pairs():
    here = os.path.dirname(os.path.abspath(__file__))
    pairs = []
    with open(os.path.join(here, "protected.sha256")) as fh:
        for ln in fh:
            if ln.strip():
                digest, path = ln.split(None, 1)
                pairs.append((digest, path.strip()))
    return pairs
