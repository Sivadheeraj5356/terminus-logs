"""Build-artifact cache read delegation under a deferred demand charge, judged by real state and access.

These read the group and filesystem state back with getent, stat and getfacl, and then switch to each
runner and job account with runuser to attempt the exact reads and writes the delegation allows or
forbids, so the verdict is the effective access the kernel computes, not a description of it. The settled
tier of every cache is re-solved here from the same inputs the grader can read (the seeded tier rosters
via getent, each cache's required and forbidden jobs, escalation order and weight from the policy
charter, and the budgets and settle_delay from tier.conf), so the expected assignment is the output of
the deferred settle rather than a frozen table. The settle is re-solved a second time with settle_delay
forced to zero to confirm the deferred window is load-bearing and a naive instant-charge answer cannot
match the shipped state.
"""
import grp
import os
import pwd
import stat
import subprocess
from collections import defaultdict

CACHE = "/srv/ci-cache"
CONF = "/app/tier.conf"

JOBS = ["job1", "job2", "job3", "job4", "job5", "job6"]
RUNNERS = ["runA", "runB", "runC", "runD"]
TIERS = ["rgW", "rgX", "rgY", "rgZ"]

# The policy charter (cache_policy.md section 3): writer, required, forbidden, escalation order, weight,
# placement order. This is the task's contract, not the answer; the settled tier of each cache is the
# deferred-settle fixed point solved from it below.
CHARTER = {
    "lint":   dict(writer="runA", req={"job3"}, forb={"job5"},         esc=["rgW", "rgX"], w=3, order=1),
    "api":    dict(writer="runB", req={"job6"}, forb={"job2"},         esc=["rgW", "rgY"], w=3, order=2),
    "web":    dict(writer="runA", req={"job6"}, forb={"job5"},         esc=["rgW", "rgX", "rgY"], w=1, order=3),
    "infra":  dict(writer="runB", req={"job2"}, forb={"job4"},         esc=["rgX", "rgZ"], w=3, order=4),
    "data":   dict(writer="runC", req={"job3"}, forb={"job4", "job5"}, esc=["rgW", "rgX"], w=2, order=5),
    "mobile": dict(writer="runC", req={"job6"}, forb={"job1"},         esc=["rgX", "rgZ"], w=1, order=6),
    "ml":     dict(writer="runD", req={"job6"}, forb={"job1", "job4"}, esc=["rgX", "rgZ"], w=1, order=7),
    "docs":   dict(writer="runD", req={"job6"}, forb={"job4"},         esc=["rgW", "rgX", "rgZ"], w=1, order=8),
}
CACHES = list(CHARTER)


def path_of(name):
    return os.path.join(CACHE, name)


def tier_roster(name):
    """Read a tier's seeded roster back off the host with getent."""
    out = subprocess.run(["getent", "group", name], capture_output=True, text=True, check=True).stdout
    members = out.strip().split(":")[3]
    return set(m for m in members.split(",") if m)


def _read_conf():
    budgets = {"rgZ": 10 ** 12}
    delay = None
    with open(CONF) as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip()
            if "=" not in line:
                continue
            k, v = (x.strip() for x in line.split("=", 1))
            if k in ("rgW_budget", "rgX_budget", "rgY_budget"):
                budgets[k.split("_")[0]] = int(v)
            elif k == "settle_delay":
                delay = int(v)
    for g in ("rgW", "rgX", "rgY"):
        assert g in budgets, f"tier.conf missing {g}_budget"
    assert delay is not None, "tier.conf missing settle_delay"
    return budgets, delay


def _legal(name, rosters):
    """The tiers whose seeded roster covers the cache's required jobs and holds none of its forbidden
    jobs. The charter escalation order must list exactly these."""
    c = CHARTER[name]
    return {g for g in TIERS if c["req"] <= rosters[g] and not (c["forb"] & rosters[g])}


def settle(rosters, budgets, settle_delay):
    """Deferred demand-charge settle to a fixed point: a placement charges its tier settle_delay
    placements later; an over-budget bounded tier turns away its latest-placed occupant, which re-settles
    to the next legal tier in its escalation order and carries its own deferred charge."""
    order = sorted(CACHES, key=lambda s: CHARTER[s]["order"])
    floor = {s: 0 for s in CACHES}

    def run_pass():
        landed = defaultdict(int)
        pending = []
        place = {}
        step = 0
        for s in order:
            for (ls, g, wt) in pending:
                if ls <= step:
                    landed[g] += wt
            pending = [p for p in pending if p[0] > step]
            esc = CHARTER[s]["esc"]
            w = CHARTER[s]["w"]
            gi = floor[s]
            while gi < len(esc):
                g = esc[gi]
                if landed[g] + w <= budgets[g]:
                    break
                gi += 1
            gi = min(gi, len(esc) - 1)
            g = esc[gi]
            place[s] = g
            pending.append((step + settle_delay, g, w))
            step += 1
        return place

    for _ in range(300):
        place = run_pass()
        tot = defaultdict(int)
        members = defaultdict(list)
        for s in order:
            tot[place[s]] += CHARTER[s]["w"]
            members[place[s]].append(s)
        over = next((g for g in ("rgW", "rgX", "rgY") if tot[g] > budgets[g]), None)
        if over is None:
            return place
        victim = max(members[over], key=lambda s: CHARTER[s]["order"])
        esc = CHARTER[victim]["esc"]
        cur = esc.index(place[victim])
        if cur + 1 < len(esc):
            floor[victim] = cur + 1
        else:
            return place
    return place


def _settled():
    rosters = {g: tier_roster(g) for g in TIERS}
    budgets, delay = _read_conf()
    return settle(rosters, budgets, delay)


def _acl_group_entries(path):
    """group qualifier -> effective (r, w, x) for every named-group ACL entry, entry AND mask."""
    out = subprocess.run(["getfacl", "-pE", path], capture_output=True, text=True, check=True).stdout
    mask = None
    for line in out.splitlines():
        p = line.strip().split(":")
        if p and p[0] == "mask":
            m = p[-1][:3]
            mask = (1 if "r" in m else 0, 1 if "w" in m else 0, 1 if "x" in m else 0)
    eff = {}
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "default:")):
            continue
        p = line.split(":")
        if len(p) < 3 or p[0] != "group" or not p[1]:
            continue
        perm = p[2][:3]
        b = (1 if "r" in perm else 0, 1 if "w" in perm else 0, 1 if "x" in perm else 0)
        eff[p[1]] = tuple(x & mk for x, mk in zip(b, mask)) if mask else b
    return eff


def can_read(acct, path):
    r = subprocess.run(["runuser", "-u", acct, "--", "cat", path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return r.returncode == 0


def can_write_new(acct, dirpath, name, um="0022"):
    r = subprocess.run(["runuser", "-u", acct, "--", "bash", "-c",
                        f"umask {um}; printf x > {os.path.join(dirpath, name)!r}"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return r.returncode == 0


def can_append(acct, path):
    r = subprocess.run(["runuser", "-u", acct, "--", "bash", "-c", f"printf '' >> {path!r}"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return r.returncode == 0


def created_groups():
    ordinary = {g.gr_name for g in grp.getgrall() if 1000 <= g.gr_gid < 65534}
    shipped = set(JOBS) | set(RUNNERS) | set(TIERS)
    return ordinary - shipped


class TestTierGroupsUnchanged:
    def test_no_new_groups_created(self):
        """The agent adds no groups: exactly the seeded jobs, runners and tiers exist, catching a solver
        that invents a per-cache group instead of riding a shared roster."""
        assert created_groups() == set(), f"unexpected groups created: {sorted(created_groups())}"

    def test_tier_rosters_untouched(self):
        """Each tier still carries exactly its seeded roster; the agent edits no membership."""
        expect = {
            "rgW": {"job1", "job3", "job6"},
            "rgX": {"job2", "job3", "job6"},
            "rgY": {"job1", "job4", "job6"},
            "rgZ": {"job2", "job5", "job6"},
        }
        for g, roster in expect.items():
            got = tier_roster(g)
            assert got == roster, f"{g} roster {sorted(got)} != seeded {sorted(roster)}"

    def test_job_primary_groups_unchanged(self):
        """Each job keeps its own private primary group of the same name."""
        for acct in JOBS:
            pg = grp.getgrgid(pwd.getpwnam(acct).pw_gid).gr_name
            assert pg == acct, f"{acct} primary group is {pg}, expected {acct}"


class TestCharterIsConsistent:
    def test_escalation_lists_exactly_legal_tiers(self):
        """Every cache's escalation column is exactly the tiers legal for it (roster covers its required
        jobs, excludes its forbidden jobs), so the anti-monotone leak bounds the fallback and a forbidden
        job can never appear in a settled roster."""
        rosters = {g: tier_roster(g) for g in TIERS}
        for name in CACHES:
            assert set(CHARTER[name]["esc"]) == _legal(name, rosters), \
                f"{name} escalation {CHARTER[name]['esc']} != legal {sorted(_legal(name, rosters))}"


class TestOwnershipAndMode:
    def test_owner_root_group_is_writer(self):
        """Each cache stays owned by root and is group-owned by its writer runner's private group, so
        setgid stamps the writer group onto every drop and no tier owns the directory."""
        for name, c in CHARTER.items():
            st = os.stat(path_of(name))
            assert pwd.getpwuid(st.st_uid).pw_name == "root", f"{name} owner not root"
            g = grp.getgrgid(st.st_gid).gr_name
            assert g == c["writer"], f"{name} group-owner {g}, writer is {c['writer']}"

    def test_setgid_and_mode_2770(self):
        """Each cache is mode 2770: setgid set, group rwx for the writer, other closed."""
        for name in CACHES:
            m = stat.S_IMODE(os.stat(path_of(name)).st_mode)
            assert m == 0o2770, f"{name} mode {oct(m)} != 2770"

    def test_other_bits_closed(self):
        for name in CACHES:
            m = stat.S_IMODE(os.stat(path_of(name)).st_mode)
            assert m & 0o007 == 0, f"{name} grants other access"


def _settled_group_check_for(name):
    """One test per cache: the directory names exactly its settled tier for traverse (r-x) and names no
    other tier, so a cache delegated through the wrong roster fails on its own."""
    def check(self):
        placement = _settled()
        entries = _acl_group_entries(path_of(name))
        named_tier = {g for g in entries if g in TIERS}
        assert named_tier == {placement[name]}, \
            f"{name} names tiers {sorted(named_tier)}, settled tier is {placement[name]}"
        assert entries[placement[name]] == (1, 0, 1), \
            f"{name} tier entry effective {entries[placement[name]]} != read+traverse only"

    check.__doc__ = f"{name} names exactly its settled tier on the directory at read+traverse."
    return check


class TestSettledTierPerCache:
    """One settled-tier directory readback per cache, so a wrongly delegated cache fails on its own."""


for _n in CACHES:
    setattr(TestSettledTierPerCache, f"test_settled_tier_{_n}", _settled_group_check_for(_n))


class TestSettleIsForced:
    def test_settled_budgets_respected(self):
        """The demand weight settled in each bounded tier stays within its budget."""
        budgets, _delay = _read_conf()
        placement = _settled()
        tot = defaultdict(int)
        for s in CACHES:
            tot[placement[s]] += CHARTER[s]["w"]
        for g in ("rgW", "rgX", "rgY"):
            assert tot[g] <= budgets[g], f"{g} settled weight {tot[g]} > budget {budgets[g]}"

    def test_a_bounded_tier_is_full(self):
        """At least one bounded tier settles at exactly its budget, so the contention that forces caches
        down their escalation chains is real, not decorative."""
        budgets, _delay = _read_conf()
        placement = _settled()
        tot = defaultdict(int)
        for s in CACHES:
            tot[placement[s]] += CHARTER[s]["w"]
        assert any(tot[g] == budgets[g] for g in ("rgW", "rgX", "rgY")), \
            f"no bounded tier reached its budget: {dict(tot)}"


def _access_check_for(name):
    """One real allow/deny row per cache: the writer drops and reads a new artifact, every required job
    and every settled roster job reads it but cannot write, every forbidden or unrelated job is fully
    denied."""
    def check(self):
        placement = _settled()
        d = path_of(name)
        c = CHARTER[name]
        roster = tier_roster(placement[name])
        assert can_write_new(c["writer"], d, f"art_{name}"), f"{c['writer']} cannot drop in {name}"
        probe = os.path.join(d, f"art_{name}")
        assert can_read(c["writer"], probe), f"{c['writer']} cannot read its own artifact in {name}"
        for m in c["req"]:
            assert can_read(m, probe), f"required job {m} cannot read {name}"
        for m in roster:
            assert can_read(m, probe), f"roster job {m} cannot read {name}"
            assert not can_append(m, probe), f"roster job {m} can write {name} (read only)"
        for m in JOBS:
            if m in roster:
                continue
            assert not can_read(m, probe), f"{m} can read {name} but is not in the settled roster"
            assert not can_append(m, probe), f"{m} can write {name} but is not the writer"
        for m in c["forb"]:
            assert m not in roster, f"forbidden job {m} is in the settled roster of {name}"

    check.__doc__ = (f"{name}: writer drops and reads an artifact, the settled roster reads only, every "
                     f"forbidden and unrelated job is denied, judged by switching to each account.")
    return check


class TestRealAccessMatrix:
    """One real allow/deny access test per cache, run by switching to each account with runuser."""


for _n in CACHES:
    setattr(TestRealAccessMatrix, f"test_access_{_n}", _access_check_for(_n))


class TestDeferredChargeIsLoadBearing:
    def test_instant_charge_moves_at_least_three_caches(self):
        """Reading the demand charge as instant (settle_delay 0) instead of deferred changes the settled
        tier of at least three caches, so the deferred window is load-bearing and a naive single-pass
        answer cannot match the shipped state."""
        rosters = {g: tier_roster(g) for g in TIERS}
        budgets, delay = _read_conf()
        real = settle(rosters, budgets, delay)
        instant = settle(rosters, budgets, 0)
        moved = [s for s in CACHES if real[s] != instant[s]]
        assert len(moved) >= 3, f"deferred charge only moved {moved}; not load-bearing"

    def test_shipped_state_matches_deferred_everywhere(self):
        """The on-disk delegated tier of every cache matches the deferred settle recomputed under the
        live settle_delay."""
        real = _settled()
        for name in CACHES:
            named = {g for g in _acl_group_entries(path_of(name)) if g in TIERS}
            assert named == {real[name]}, f"{name}: disk names {sorted(named)}, deferred says {real[name]}"


def _not_instant_check_for(name):
    """One test per cache the deferred charge moves: the on-disk tier must NOT be the instant-charge tier,
    so a solver that charges placements immediately fails here."""
    def check(self):
        rosters = {g: tier_roster(g) for g in TIERS}
        budgets, delay = _read_conf()
        real = settle(rosters, budgets, delay)
        instant = settle(rosters, budgets, 0)
        if real[name] == instant[name]:
            return  # this cache is not one the charge moves; nothing to discriminate
        named = {g for g in _acl_group_entries(path_of(name)) if g in TIERS}.pop()
        assert named != instant[name], \
            f"{name}: disk matches the instant-charge tier {instant[name]} (deferred ignored)"

    check.__doc__ = (f"{name}: on-disk delegated tier is the deferred settle, not the instant-charge "
                     f"tier, so an instant-charge solver fails here.")
    return check


class TestMovedCachesFollowDeferredNotInstant:
    """One test per cache, failing under an instant-charge solver on the caches the deferral moves."""


for _n in CACHES:
    setattr(TestMovedCachesFollowDeferredNotInstant, f"test_not_instant_{_n}", _not_instant_check_for(_n))


def _drop_as_writer(name, um, kind, probe):
    writer = CHARTER[name]["writer"]
    d = path_of(name)
    target = os.path.join(d, probe)
    mk = f"mkdir {target!r}" if kind == "dir" else f"touch {target!r}"
    subprocess.run(["runuser", "-u", writer, "--", "bash", "-c", f"umask {um}; {mk}"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return target


class TestDropInheritanceUnderUmask:
    """Every artifact file and subdirectory a runner drops must come out writer-writable and tier read
    only, holding under a restrictive umask. This is the default-ACL mask against each entry's own create
    mode: a new file folds its mask below execute, a new subdirectory keeps traverse."""

    def test_new_file_tier_read_only_any_umask(self):
        """A plain artifact file dropped under umask 0022 and 0077 lands with the settled tier effective
        read only (no write, no execute) while the writer keeps write."""
        placement = _settled()
        for name in CACHES:
            tier = placement[name]
            for i, um in enumerate(("0022", "0077")):
                f = _drop_as_writer(name, um, "file", f"probe_f_{i}")
                assert os.path.isfile(f), f"{name}: writer could not drop a file under umask {um}"
                assert grp.getgrgid(os.stat(f).st_gid).gr_name == CHARTER[name]["writer"], \
                    f"{name}: dropped file not group {CHARTER[name]['writer']}"
                eff = _acl_group_entries(f).get(tier)
                assert eff == (1, 0, 0), f"{name} file under umask {um}: {tier} effective {eff} != r--"

    def test_new_subdir_tier_read_traverse_any_umask(self):
        """A subdirectory dropped under umask 0022 and 0077 lands with the settled tier effective read
        and traverse but never write, so the roster can descend a bundle without changing it."""
        placement = _settled()
        for name in CACHES:
            tier = placement[name]
            for i, um in enumerate(("0022", "0077")):
                d = _drop_as_writer(name, um, "dir", f"probe_d_{i}")
                assert os.path.isdir(d), f"{name}: writer could not drop a dir under umask {um}"
                eff = _acl_group_entries(d).get(tier)
                assert eff == (1, 0, 1), f"{name} subdir under umask {um}: {tier} effective {eff} != r-x"

    def test_tier_member_cannot_write_a_new_drop(self):
        """Effective access, not metadata: a real settled-roster member reads a freshly dropped artifact
        but cannot write it, under umask 0077."""
        placement = _settled()
        for name in CACHES:
            member = sorted(tier_roster(placement[name]))[0]
            f = _drop_as_writer(name, "0077", "file", "probe_realaccess")
            assert os.path.isfile(f), f"{name}: could not drop probe for real-access check"
            assert can_read(member, f), f"{name}: roster member {member} should read a new drop"
            assert not can_append(member, f), f"{name}: roster member {member} must not write a new drop"


class TestNoDefaultGroupWriteLeak:
    def test_no_tier_default_group_write(self):
        """No cache leaks default group write to its settled roster: the tier's default entry is read and
        traverse only, so a solver that hands the tier a group-write default fails."""
        placement = _settled()
        for name in CACHES:
            tier = placement[name]
            out = subprocess.run(["getfacl", "-p", path_of(name)],
                                 capture_output=True, text=True, check=True).stdout
            for line in out.splitlines():
                if line.startswith(f"default:group:{tier}:"):
                    perm = line.split(":")[3][:3]
                    assert "w" not in perm, f"{name} default tier entry {perm} grants write"


class TestFailClosed:
    def test_forbidden_write_returns_nonzero(self):
        """A forbidden job's write attempt really fails: runuser exits nonzero. lint forbids job5, which
        is not in lint's settled roster, so job5 cannot drop into the cache."""
        d = path_of("lint")
        proc = subprocess.run(
            ["runuser", "-u", "job5", "--", "bash", "-c", f"printf x > {os.path.join(d, 'evil')!r}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        assert proc.returncode != 0, "job5 (forbidden) drop into lint should fail"

    def test_host_is_present_fail_closed(self):
        """Refuse to score without the real host state: every cache, job, runner and the conf."""
        for name in CACHES:
            assert os.path.isdir(path_of(name)), f"{path_of(name)} missing"
        for acct in JOBS + RUNNERS:
            pwd.getpwnam(acct)
        assert os.path.isfile(CONF), "tier.conf missing"
