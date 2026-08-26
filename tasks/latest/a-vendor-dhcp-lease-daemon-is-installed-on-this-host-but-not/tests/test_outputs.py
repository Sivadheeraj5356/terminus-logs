"""Acceptance tests for a provisioned, hardened DHCP lease appliance.

Concerns checked in one place:

* TestServiceProvisioning - the host administration: a dedicated service
  account; private state, log, and backup directories with the right ownership
  and restrictive permissions; the administrative and maintenance commands on
  PATH; the initialised database provisioned with the three required pools and
  their reservations and nothing else; log rotation; and the three scheduled
  maintenance jobs.
* TestLeaseOperations - the leasing behaviour of the running service, driven
  through the installed ``dhcpdctl`` command against a throwaway database.
* TestBackupRestore / TestReport / TestProvisionIdempotent - the backup,
  restore, reporting, and idempotent-provisioning maintenance tooling.
* TestLeaseReaper - the scheduled maintenance job that clears expired leases.
"""
import glob
import grp
import hashlib
import hmac
import itertools
import json
import os
import pwd
import re
import shutil
import stat
import subprocess
import tempfile

_net = itertools.count(1)
LIVE_DB = "/var/lib/dhcpd/dhcp.db"


class Resp:
    def __init__(self, code, body):
        self.code = code
        self.body = body


def call(req, env=None):
    """Run one JSON request through the installed dhcpdctl command."""
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(req, f)
    try:
        p = subprocess.run(["dhcpdctl", path], capture_output=True, text=True,
                           timeout=15, env=env)
    finally:
        os.unlink(path)
    d = json.loads(p.stdout or "{}")
    return Resp(d.pop("code", 0), d)


def new_pool(lease_secs=3600, reserved_offsets=None, reservations=None, prefix=29):
    """Create a pool on a fresh 10.N.0.0/prefix network, optionally excluding
    reserved_offsets and pinning reservations [(offset, client_id), ...]; returns
    (pool_id, base) where base is the '10.N.0' network prefix."""
    n = next(_net)
    base = f"10.{n}.0"
    reserved = [f"{base}.{o}" for o in (reserved_offsets or [])]
    reserved += [{"ip": f"{base}.{o}", "client_id": c} for (o, c) in (reservations or [])]
    r = call({"op": "create_pool", "cidr": f"{base}.0/{prefix}",
              "lease_secs": lease_secs, "reserved": reserved})
    assert r.code == 201, r.body
    return r.body["pool_id"], base


def do_lease(pid, client, **kw):
    """Request a lease for client on pool pid; extra kwargs (e.g. requested, now_ms)
    pass straight into the request body."""
    return call({"op": "lease", "pool_id": pid, "client_id": client, **kw})


def do_renew(ip, client, **kw):
    """Renew the lease held by client on address ip (extra kwargs pass through)."""
    return call({"op": "renew", "ip": ip, "client_id": client, **kw})


def do_release(ip):
    """Release the lease on ip, returning the address to the free pool."""
    return call({"op": "release", "ip": ip})


def do_decline(ip):
    """Mark ip as declined so it is withheld from future offers."""
    return call({"op": "decline", "ip": ip})


def _stat_owner(path):
    """Return (owner_user, owner_group) names for path."""
    st = os.stat(path)
    return pwd.getpwuid(st.st_uid).pw_name, grp.getgrgid(st.st_gid).gr_name


def _mode(path):
    """Return the permission bits of path as an integer (e.g. 0o750)."""
    return stat.S_IMODE(os.stat(path).st_mode)


def _reap(now_ms):
    """Run the reaper as of the given epoch-millis clock (via DHCPD_NOW_MS)."""
    subprocess.run(["dhcpd-reap"], check=True, capture_output=True, text=True,
                   env={**os.environ, "DHCPD_NOW_MS": str(now_ms)})


def _lease_count():
    """Return the number of rows in the leases table of the scratch DHCPD_DB."""
    out = subprocess.run(["sqlite3", os.environ["DHCPD_DB"], "SELECT COUNT(*) FROM leases;"],
                         capture_output=True, text=True)
    return int(out.stdout.strip() or "0")


def _ip_to_int(s):
    """Convert a dotted-quad IPv4 string to its 32-bit integer value."""
    a, b, c, d = (int(x) for x in s.split("."))
    return (a << 24) | (b << 16) | (c << 8) | d


def _live_sql(sql):
    """Run a read-only query against the live service database and return stdout."""
    return subprocess.run(["sqlite3", LIVE_DB, sql],
                          capture_output=True, text=True).stdout.strip()


def _live_pools():
    rows = _live_sql("SELECT id,cidr,lease_secs FROM pools ORDER BY id;").splitlines()
    return {c: (int(i), int(lease)) for i, c, lease in (r.split("|") for r in rows if r)}


def _cron_all():
    d = "/etc/cron.d"
    txt = ""
    for f in os.listdir(d):
        p = os.path.join(d, f)
        if os.path.isfile(p):
            txt += open(p).read() + "\n"
    return txt


class TestServiceProvisioning:
    """The host must be administered into a running, hardened, self-contained service."""

    def test_service_group_exists(self):
        """The dhcpd service group exists."""
        grp.getgrnam("dhcpd")

    def test_service_user_is_unprivileged_system_account(self):
        """The dhcpd user is an unprivileged system account with the service home and a non-login shell."""
        u = pwd.getpwnam("dhcpd")
        assert u.pw_uid < 1000, "the service account must be a system user"
        assert u.pw_gid == grp.getgrnam("dhcpd").gr_gid
        assert u.pw_dir == "/var/lib/dhcpd"
        assert os.path.basename(u.pw_shell) in ("nologin", "false")

    def test_state_directory_owned_and_private(self):
        """The state directory exists, is owned dhcpd:dhcpd, and is mode 0750."""
        assert os.path.isdir("/var/lib/dhcpd")
        assert _stat_owner("/var/lib/dhcpd") == ("dhcpd", "dhcpd")
        assert _mode("/var/lib/dhcpd") == 0o750

    def test_log_directory_owned_and_private(self):
        """The log directory must be owned by the service account AND restrictive
        (mode 0750), not left world-readable."""
        assert os.path.isdir("/var/log/dhcpd")
        assert _stat_owner("/var/log/dhcpd") == ("dhcpd", "dhcpd")
        assert _mode("/var/log/dhcpd") == 0o750

    def test_backup_directory_owned_and_private(self):
        """The backup directory exists, is owned dhcpd:dhcpd, and is mode 0700."""
        d = "/var/lib/dhcpd/backups"
        assert os.path.isdir(d), "the backup directory must exist"
        assert _stat_owner(d) == ("dhcpd", "dhcpd")
        assert _mode(d) == 0o700

    def test_state_database_owned_by_service(self):
        """The lease database exists and is owned dhcpd:dhcpd."""
        assert os.path.isfile(LIVE_DB)
        assert _stat_owner(LIVE_DB) == ("dhcpd", "dhcpd")

    def test_state_database_not_world_accessible(self):
        """The lease database holds lease and audit state and must not be readable
        or writable by other (mode 0640 or stricter)."""
        m = _mode(LIVE_DB)
        assert m & 0o007 == 0, oct(m)
        assert m in (0o640, 0o600), oct(m)

    def test_admin_command_on_path(self):
        """dhcpdctl is installed on PATH and executable."""
        p = shutil.which("dhcpdctl")
        assert p is not None, "dhcpdctl must be installed on PATH"
        assert os.access(p, os.X_OK)

    def test_maintenance_commands_installed(self):
        """All seven administrative commands are installed on PATH and executable."""
        for cmd in ("dhcpd-provision", "dhcpd-reap", "dhcpd-backup",
                    "dhcpd-restore", "dhcpd-report", "dhcpd-check", "dhcpd-fsck"):
            p = shutil.which(cmd)
            assert p is not None and os.access(p, os.X_OK), cmd

    def test_pool_configuration_present(self):
        """The pool definitions directory holds at least one JSON pool file."""
        d = "/etc/dhcpd/pools.d"
        assert os.path.isdir(d)
        assert [f for f in os.listdir(d) if f.endswith(".json")], "no pool definitions"

    def test_service_config_file_declares_paths(self):
        """A single configuration file the commands read declares the state
        database, pool directory, log directory, and backup directory."""
        conf = "/etc/dhcpd/dhcpd.conf"
        assert os.path.isfile(conf)
        cfg = {}
        for line in open(conf):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
        assert cfg.get("STATE_DB") == LIVE_DB, cfg
        for key in ("POOL_DIR", "LOG_DIR", "BACKUP_DIR"):
            assert cfg.get(key), (key, cfg)

    def test_maintenance_jobs_scheduled_as_service(self):
        """The reaper, backup, report, and drift-check jobs must all be scheduled
        in the system crontab, each running as the dhcpd account."""
        txt = _cron_all()
        for cmd in ("dhcpd-reap", "dhcpd-backup", "dhcpd-report"):
            assert re.search(
                r"^\s*[\d*/,\-]+(\s+[\d*/,\-]+){4}\s+dhcpd\s+.*" + re.escape(cmd), txt, re.M
            ), f"no valid cron schedule running {cmd} as dhcpd"
        # The fourth maintenance job runs the non-mutating drift check.
        assert re.search(
            r"^\s*[\d*/,\-]+(\s+[\d*/,\-]+){4}\s+dhcpd\s+.*dhcpd-provision\s+--check", txt, re.M
        ), "no cron schedule running dhcpd-provision --check as dhcpd"

    def test_logrotate_configured(self):
        """A logrotate policy must rotate the service logs as the dhcpd account,
        keep at least 14 rotations, compress, and parse cleanly."""
        path = "/etc/logrotate.d/dhcpd"
        assert os.path.isfile(path)
        text = open(path).read()
        assert "/var/log/dhcpd" in text
        assert re.search(r"\bsu\s+dhcpd\s+dhcpd\b", text), "must rotate as the dhcpd account"
        assert re.search(r"\bdaily\b", text)
        assert "compress" in text
        m = re.search(r"\brotate\s+(\d+)", text)
        assert m and int(m.group(1)) >= 14, "must keep at least 14 rotations"
        r = subprocess.run(["logrotate", "--debug", path], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr

    def test_exactly_the_three_required_pools(self):
        """Precisely the three required pools are provisioned - no more, no fewer."""
        assert int(_live_sql("SELECT COUNT(*) FROM pools;") or 0) == 3

    def test_live_database_has_no_stray_state(self):
        """The provisioned database carries only the pool definitions and their
        reservations: no leases or declines left over from any testing."""
        for tbl in ("leases", "declines"):
            n = int(_live_sql(f"SELECT COUNT(*) FROM {tbl};") or 0)
            assert n == 0, f"{tbl} must be empty in the provisioned database, found {n}"

    def test_site_pool_is_provisioned(self):
        """The site pool 10.10.0.0/24 is provisioned with a 3600s lease, the .1 exclusion, and the printer reservation."""
        pools = _live_pools()
        assert "10.10.0.0/24" in pools, "site pool missing"
        pid, ls = pools["10.10.0.0/24"]
        assert ls == 3600
        env = {**os.environ, "DHCPD_DB": LIVE_DB}
        s = call({"op": "status", "pool_id": pid, "now_ms": 1000}, env=env)
        assert s.code == 200
        assert s.body["total"] == 254
        assert s.body["excluded"] == 1
        assert s.body["available"] == 253
        assert s.body["active"] == 0
        # The printer reservation itself must exist, not merely the 10.10.0.1
        # exclusion: an agent that omits the client-bound reservation must fail.
        assert _live_sql(
            f"SELECT ip FROM reservations WHERE pool_id={pid} AND client_id='printer';"
        ) == str(_ip_to_int("10.10.0.10"))

    def test_guest_pool_sized_and_provisioned(self):
        """The guest pool on 10.20.0.0 offers at least 1000 usable addresses with a 600s lease and the gateway withheld."""
        pools = _live_pools()
        guest = [(c, p, lease) for c, (p, lease) in pools.items() if c.startswith("10.20.0.0/")]
        assert guest, "guest pool on network 10.20.0.0 not provisioned"
        cidr, pid, ls = guest[0]
        assert ls == 600
        env = {**os.environ, "DHCPD_DB": LIVE_DB}
        s = call({"op": "status", "pool_id": pid, "now_ms": 1000}, env=env)
        assert s.body["total"] >= 1000, "guest pool must offer at least 1000 usable addresses"
        assert s.body["excluded"] == 1, "the gateway 10.20.0.1 must be withheld"
        assert s.body["active"] == 0

    def test_voip_pool_is_provisioned(self):
        """The voip pool 10.30.0.0/24 is provisioned with an 86400s lease, the .1 exclusion, and the pbx reservation."""
        pools = _live_pools()
        assert "10.30.0.0/24" in pools, "voip pool missing"
        pid, ls = pools["10.30.0.0/24"]
        assert ls == 86400
        env = {**os.environ, "DHCPD_DB": LIVE_DB}
        s = call({"op": "status", "pool_id": pid, "now_ms": 1000}, env=env)
        assert s.body["excluded"] == 1
        assert s.body["active"] == 0
        assert _live_sql(
            f"SELECT ip FROM reservations WHERE pool_id={pid} AND client_id='pbx';"
        ) == str(_ip_to_int("10.30.0.5"))


class TestLeaseOperations:
    """Leasing behaviour of the provisioned service, via dhcpdctl."""

    def test_healthz(self):
        """The daemon answers a healthz probe with 200 and status ok."""
        r = call({"op": "healthz"})
        assert r.code == 200 and r.body == {"status": "ok"}

    def test_create_pool_returns_id(self):
        """Creating a pool returns a positive integer pool id."""
        pid, _ = new_pool()
        assert isinstance(pid, int) and pid > 0

    def test_invalid_cidr_rejected(self):
        """A malformed CIDR is rejected with 400."""
        assert call({"op": "create_pool", "cidr": "not-a-cidr", "lease_secs": 60}).code == 400

    def test_missing_lease_secs_rejected(self):
        """Creating a pool without lease_secs is rejected with 400."""
        n = next(_net)
        assert call({"op": "create_pool", "cidr": f"10.{n}.0.0/29"}).code == 400

    def test_first_free_is_lowest_usable(self):
        """The first lease hands out the lowest usable address."""
        pid, base = new_pool()
        r = do_lease(pid, "alice", now_ms=1000)
        assert r.code == 200 and r.body["ip"] == f"{base}.1"

    def test_expiry_from_now_ms(self):
        """A lease expiry is now_ms plus the lease time in milliseconds."""
        pid, _ = new_pool(lease_secs=3600)
        assert do_lease(pid, "alice", now_ms=1000).body["expires_ms"] == 1000 + 3600 * 1000

    def test_reserved_address_excluded(self):
        """An excluded address is skipped when allocating."""
        pid, base = new_pool(reserved_offsets=[1])
        assert do_lease(pid, "alice", now_ms=1000).body["ip"] == f"{base}.2"

    def test_leases_ascend_across_clients(self):
        """Successive clients receive ascending addresses."""
        pid, base = new_pool()
        got = [do_lease(pid, c, now_ms=1000).body["ip"] for c in ("a", "b", "c")]
        assert got == [f"{base}.1", f"{base}.2", f"{base}.3"]

    def test_network_and_broadcast_excluded(self):
        """The network and broadcast addresses are never allocated."""
        pid, base = new_pool(prefix=30)
        got = [do_lease(pid, c, now_ms=1000).body["ip"] for c in ("a", "b")]
        assert got == [f"{base}.1", f"{base}.2"]

    def test_unknown_pool_404(self):
        """Leasing from an unknown pool returns 404."""
        assert do_lease(999999, "x", now_ms=1000).code == 404

    def test_missing_client_id_400(self):
        """A lease request without a client id returns 400."""
        pid, _ = new_pool()
        assert call({"op": "lease", "pool_id": pid, "now_ms": 1000}).code == 400

    def test_active_lease_not_reclaimed(self):
        """An address with an active lease is not reused."""
        pid, base = new_pool(lease_secs=100)
        do_lease(pid, "alice", now_ms=1000)
        assert do_lease(pid, "bob", now_ms=5000).body["ip"] == f"{base}.2"

    def test_expired_leases_reclaimed(self):
        """An expired lease frees its address for reuse."""
        pid, base = new_pool(lease_secs=10)
        for c in ("c1", "c2", "c3", "c4", "c5", "c6"):
            do_lease(pid, c, now_ms=1000)
        assert do_lease(pid, "c7", now_ms=5000).code == 409
        r = do_lease(pid, "c7", now_ms=20000)
        assert r.code == 200 and r.body["ip"] == f"{base}.1"

    def test_renew_extends_expiry(self):
        """Renewing extends the lease expiry from the new time."""
        pid, base = new_pool(lease_secs=100)
        do_lease(pid, "alice", now_ms=1000)
        r = do_renew(f"{base}.1", "alice", now_ms=5000)
        assert r.code == 200 and r.body == {"expires_ms": 5000 + 100 * 1000}

    def test_renew_wrong_client_404(self):
        """Renewing an address held by another client returns 404."""
        pid, base = new_pool()
        do_lease(pid, "alice", now_ms=1000)
        assert do_renew(f"{base}.1", "mallory", now_ms=2000).code == 404

    def test_renew_unleased_404(self):
        """Renewing an unleased address returns 404."""
        pid, base = new_pool()
        assert do_renew(f"{base}.3", "alice", now_ms=2000).code == 404

    def test_release_frees_address(self):
        """Releasing an address returns it to the free pool."""
        pid, base = new_pool(lease_secs=100)
        do_lease(pid, "alice", now_ms=1000)
        rel = do_release(f"{base}.1")
        assert rel.code == 200 and rel.body == {"released": True}
        assert do_lease(pid, "bob", now_ms=2000).body["ip"] == f"{base}.1"

    def test_release_unleased_404(self):
        """Releasing an unleased address returns 404."""
        pid, base = new_pool()
        assert do_release(f"{base}.2").code == 404

    def test_requested_beats_sticky(self):
        """A requested address wins over the client's previous sticky address."""
        pid, base = new_pool(lease_secs=100)
        assert do_lease(pid, "alice", now_ms=1000).body["ip"] == f"{base}.1"
        r = do_lease(pid, "alice", requested_ip=f"{base}.5", now_ms=2000)
        assert r.code == 200 and r.body["ip"] == f"{base}.5"

    def test_same_client_gets_same_address(self):
        """A returning client gets its previous address back."""
        pid, base = new_pool(lease_secs=100)
        first = do_lease(pid, "alice", now_ms=1000).body["ip"]
        do_lease(pid, "bob", now_ms=1000)
        again = do_lease(pid, "alice", now_ms=2000).body["ip"]
        assert again == first == f"{base}.1"

    def test_requested_ip_honoured(self):
        """A free requested address is honoured."""
        pid, base = new_pool()
        assert do_lease(pid, "alice", requested_ip=f"{base}.5", now_ms=1000).body["ip"] == f"{base}.5"

    def test_requested_taken_is_conflict(self):
        """Requesting an address held by another client returns 409 conflict."""
        pid, base = new_pool(lease_secs=100)
        do_lease(pid, "alice", now_ms=1000)
        r = do_lease(pid, "bob", requested_ip=f"{base}.1", now_ms=1000)
        assert r.code == 409 and r.body["error"] == "conflict"

    def test_sticky_reclaims_own_expired_address(self):
        """A client reclaims its own expired address."""
        pid, base = new_pool(lease_secs=10)
        do_lease(pid, "alice", now_ms=1000)
        assert do_lease(pid, "alice", now_ms=20000).body["ip"] == f"{base}.1"

    def test_requested_outside_pool_falls_back(self):
        """A requested address outside the pool falls back to the lowest free address."""
        pid, base = new_pool()
        assert do_lease(pid, "alice", requested_ip="10.200.200.200", now_ms=1000).body["ip"] == f"{base}.1"

    def test_reserved_client_gets_reserved_address(self):
        """A client with a reservation gets its reserved address."""
        pid, base = new_pool(reservations=[(3, "zoe")])
        assert do_lease(pid, "zoe", now_ms=1000).body["ip"] == f"{base}.3"

    def test_reserved_address_withheld_from_others(self):
        """A client-reserved address is withheld from other clients."""
        pid, base = new_pool(reservations=[(1, "zoe")])
        assert do_lease(pid, "eve", now_ms=1000).body["ip"] == f"{base}.2"

    def test_request_for_others_reservation_falls_back(self):
        """Requesting another client's reserved address falls back to a free one."""
        pid, base = new_pool(reservations=[(2, "zoe")])
        assert do_lease(pid, "eve", requested_ip=f"{base}.2", now_ms=1000).body["ip"] == f"{base}.1"

    def test_declined_address_never_offered(self):
        """A declined address is never offered again."""
        pid, base = new_pool()
        do_lease(pid, "alice", now_ms=1000)
        d = do_decline(f"{base}.1")
        assert d.code == 200 and d.body == {"declined": True}
        assert do_lease(pid, "bob", now_ms=2000).body["ip"] == f"{base}.2"

    def test_state_persists_across_invocations(self):
        """Lease state persists across separate command invocations."""
        pid, base = new_pool(lease_secs=1000)
        ip = do_lease(pid, "alice", now_ms=1000).body["ip"]
        r = do_lease(pid, "alice", now_ms=2000)
        assert r.code == 200 and r.body["ip"] == ip

    def test_decline_persists_across_invocations(self):
        """A decline persists across separate command invocations."""
        pid, base = new_pool()
        do_lease(pid, "alice", now_ms=1000)
        do_decline(f"{base}.1")
        assert do_lease(pid, "bob", now_ms=2000).body["ip"] == f"{base}.2"

    def test_reservation_persists_across_invocations(self):
        """A reservation persists across separate command invocations."""
        pid, base = new_pool(reservations=[(3, "zoe")])
        assert do_lease(pid, "zoe", now_ms=1000).body["ip"] == f"{base}.3"
        assert do_lease(pid, "eve", now_ms=1000).body["ip"] != f"{base}.3"

    def test_conflict_on_requested_held_address(self):
        """Requesting a currently held address returns 409 conflict."""
        pid, base = new_pool(lease_secs=1000)
        do_lease(pid, "alice", now_ms=1000)
        r = do_lease(pid, "bob", requested_ip=f"{base}.1", now_ms=2000)
        assert r.code == 409 and r.body["error"] == "conflict"

    def test_pool_exhausted(self):
        """A pool with no free addresses returns 409 pool_exhausted."""
        pid, _ = new_pool(lease_secs=1000, prefix=30)
        do_lease(pid, "a", now_ms=1000)
        do_lease(pid, "b", now_ms=1000)
        r = do_lease(pid, "c", now_ms=2000)
        assert r.code == 409 and r.body["error"] == "pool_exhausted"

    def test_exhaustion_relieved_after_expiry(self):
        """Exhaustion is relieved once leases expire."""
        pid, _ = new_pool(lease_secs=10, prefix=30)
        do_lease(pid, "a", now_ms=1000)
        do_lease(pid, "b", now_ms=1000)
        assert do_lease(pid, "c", now_ms=5000).code == 409
        assert do_lease(pid, "c", now_ms=20000).code == 200

    def test_status_reports_utilisation(self):
        """Status reports the pool total, active, available, and active leases."""
        pid, base = new_pool(lease_secs=1000)
        do_lease(pid, "a", now_ms=1000)
        do_lease(pid, "b", now_ms=1000)
        s = call({"op": "status", "pool_id": pid, "now_ms": 1000}).body
        assert s["total"] == 6
        assert s["active"] == 2
        assert s["available"] == 4
        assert [x["ip"] for x in s["leases"]] == [f"{base}.1", f"{base}.2"]

    def test_status_unknown_pool_404(self):
        """Status for an unknown pool returns 404."""
        assert call({"op": "status", "pool_id": 999999}).code == 404

    def test_audit_trail_records_events(self):
        """Mutating lease operations are recorded in the audit trail with an address and timestamp."""
        pid, base = new_pool(lease_secs=1000)
        do_lease(pid, "alice", now_ms=1000)
        call({"op": "renew", "ip": f"{base}.1", "client_id": "alice", "now_ms": 2000})
        call({"op": "release", "ip": f"{base}.1"})
        do_lease(pid, "bob", now_ms=3000)
        call({"op": "decline", "ip": f"{base}.2"})
        rows = subprocess.run(
            ["sqlite3", os.environ["DHCPD_DB"], "SELECT event, ip, ts_ms FROM audit ORDER BY id;"],
            capture_output=True, text=True).stdout.strip().splitlines()
        events = [row.split("|")[0] for row in rows]
        for want in ("lease", "renew", "release", "decline"):
            assert want in events, (want, events)
        for row in rows:
            _ev, ip, ts = row.split("|")
            assert ip != "" and int(ts) > 0, row


class TestBackupRestore:
    """The backup command snapshots the database privately and restore round-trips."""

    def test_backup_creates_private_snapshot(self, tmp_path):
        """A backup writes a private mode-0600 SQL dump of the database."""
        pid, base = new_pool(lease_secs=1000)
        do_lease(pid, "alice", now_ms=1000)
        env = {**os.environ, "DHCPD_BACKUP_DIR": str(tmp_path)}
        p = subprocess.run(["dhcpd-backup"], capture_output=True, text=True,
                           env=env, check=True)
        path = p.stdout.strip()
        assert os.path.isfile(path), path
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
        assert "CREATE TABLE" in open(path).read()

    def test_restore_round_trips_lost_state(self, tmp_path):
        """A restore recovers lease state lost from the database."""
        pid, base = new_pool(lease_secs=1000)
        ip = do_lease(pid, "alice", now_ms=1000).body["ip"]
        env = {**os.environ, "DHCPD_BACKUP_DIR": str(tmp_path)}
        path = subprocess.run(["dhcpd-backup"], capture_output=True, text=True,
                              env=env, check=True).stdout.strip()
        # Simulate loss: wipe all leases from the live scratch database.
        subprocess.run(["sqlite3", os.environ["DHCPD_DB"], "DELETE FROM leases;"], check=True)
        assert call({"op": "status", "pool_id": pid, "now_ms": 1000}).body["active"] == 0
        subprocess.run(["dhcpd-restore", path], check=True, capture_output=True, text=True)
        s = call({"op": "status", "pool_id": pid, "now_ms": 1000}).body
        assert s["active"] == 1
        assert [x["ip"] for x in s["leases"]] == [ip]


class TestReport:
    """The report command emits per-pool utilisation for every pool."""

    def test_report_lists_every_pool_with_utilisation(self):
        """The report emits per-pool total, active, available, utilisation, and CIDR for every pool."""
        pid1, base1 = new_pool(lease_secs=1000)   # /29 -> 6 usable
        do_lease(pid1, "a", now_ms=1000)
        do_lease(pid1, "b", now_ms=1000)
        pid2, _ = new_pool(lease_secs=1000)
        out = subprocess.run(["dhcpd-report"], capture_output=True, text=True,
                             env={**os.environ, "DHCPD_NOW_MS": "1000"}, check=True)
        rows = [json.loads(line) for line in out.stdout.splitlines() if line.strip()]
        by = {r["pool_id"]: r for r in rows}
        assert pid1 in by and pid2 in by
        assert by[pid1]["total"] == 6
        assert by[pid1]["active"] == 2
        assert by[pid1]["available"] == 4
        assert by[pid1]["utilization"] == 33   # 2 * 100 / 6
        assert by[pid1]["cidr"] == f"{base1}.0/29"
        assert by[pid2]["active"] == 0


class TestProvisionIdempotent:
    """Re-running the provisioner must not duplicate pools already loaded."""

    def test_provision_is_idempotent(self, tmp_path):
        """Re-running the provisioner does not duplicate an already-loaded pool."""
        pd = tmp_path / "pools.d"
        pd.mkdir()
        (pd / "lan.json").write_text(json.dumps(
            {"op": "create_pool", "cidr": "10.77.0.0/24", "lease_secs": 3600,
             "reserved": ["10.77.0.1"]}))
        env = {**os.environ, "DHCPD_POOLS_DIR": str(pd)}
        subprocess.run(["dhcpd-provision"], check=True, env=env, capture_output=True, text=True)
        subprocess.run(["dhcpd-provision"], check=True, env=env, capture_output=True, text=True)
        n = int(subprocess.run(
            ["sqlite3", os.environ["DHCPD_DB"],
             "SELECT COUNT(*) FROM pools WHERE cidr='10.77.0.0/24';"],
            capture_output=True, text=True).stdout.strip() or 0)
        assert n == 1, f"provisioning must be idempotent, found {n} pools"


class TestLeaseReaper:
    """The cron-driven reaper clears expired leases and keeps live ones."""

    def test_reaper_drops_only_expired_leases(self):
        """The reaper deletes expired leases and keeps live ones."""
        pid, _ = new_pool(lease_secs=10)
        do_lease(pid, "alice", now_ms=1000)          # expires at 11000
        pid2, _ = new_pool(lease_secs=100000)
        do_lease(pid2, "bob", now_ms=1000)           # expires at 100001000
        assert _lease_count() == 2
        _reap(50000)                                 # 11000 <= 50000 < 100001000
        assert _lease_count() == 1

    def test_reaper_keeps_live_leases(self):
        """The reaper leaves a still-valid lease in place."""
        pid, _ = new_pool(lease_secs=100)
        do_lease(pid, "alice", now_ms=1000)          # expires at 101000
        _reap(50000)                                 # still valid
        assert _lease_count() == 1


# ---- helpers for the reconciliation and backup-integrity tests --------------
def _provision(pools_dir):
    subprocess.run(["dhcpd-provision"], check=True, capture_output=True, text=True,
                   env={**os.environ, "DHCPD_POOLS_DIR": str(pools_dir)})


def _scratch_pools():
    out = subprocess.run(["sqlite3", os.environ["DHCPD_DB"],
                          "SELECT cidr||'|'||lease_secs FROM pools ORDER BY cidr;"],
                         capture_output=True, text=True).stdout.strip().splitlines()
    return dict(line.split("|") for line in out if line)


def _pool_rows(cidr):
    return int(subprocess.run(["sqlite3", os.environ["DHCPD_DB"],
                               f"SELECT COUNT(*) FROM pools WHERE cidr='{cidr}';"],
                              capture_output=True, text=True).stdout.strip() or 0)


def _pool_file(d, name, cidr, lease_secs, reserved=None):
    (d / name).write_text(json.dumps(
        {"op": "create_pool", "cidr": cidr, "lease_secs": lease_secs,
         "reserved": reserved or []}))


class TestReconciliation:
    """Provisioning reconciles the live pools to exactly the declared set:
    creating the new, updating a changed lease time, and removing what is gone."""

    def test_creates_and_is_idempotent(self, tmp_path):
        """Provisioning creates a declared pool and does not duplicate it on re-run."""
        pd = tmp_path / "pools.d"
        pd.mkdir()
        _pool_file(pd, "a.json", "10.50.0.0/24", 3600)
        _provision(pd)
        _provision(pd)
        assert _scratch_pools().get("10.50.0.0/24") == "3600"
        assert _pool_rows("10.50.0.0/24") == 1   # never duplicated

    def test_updates_changed_lease_time(self, tmp_path):
        """Provisioning updates a pool whose declared lease time changed."""
        pd = tmp_path / "pools.d"
        pd.mkdir()
        _pool_file(pd, "a.json", "10.51.0.0/24", 3600)
        _provision(pd)
        _pool_file(pd, "a.json", "10.51.0.0/24", 7200)   # lease time changed
        _provision(pd)
        assert _scratch_pools()["10.51.0.0/24"] == "7200"
        assert _pool_rows("10.51.0.0/24") == 1

    def test_removes_undeclared_pool(self, tmp_path):
        """Provisioning removes a pool that is no longer declared."""
        pd = tmp_path / "pools.d"
        pd.mkdir()
        _pool_file(pd, "a.json", "10.52.0.0/24", 3600)
        _pool_file(pd, "b.json", "10.53.0.0/24", 600)
        _provision(pd)
        assert set(_scratch_pools()) == {"10.52.0.0/24", "10.53.0.0/24"}
        (pd / "b.json").unlink()                         # declaration dropped
        _provision(pd)
        assert set(_scratch_pools()) == {"10.52.0.0/24"}

    def test_removal_cascades_leases(self, tmp_path):
        """Removing a pool cascades to delete its leases."""
        pd = tmp_path / "pools.d"
        pd.mkdir()
        _pool_file(pd, "a.json", "10.54.0.0/24", 3600)
        _provision(pd)
        pid = int(subprocess.run(["sqlite3", os.environ["DHCPD_DB"],
                                  "SELECT id FROM pools WHERE cidr='10.54.0.0/24';"],
                                 capture_output=True, text=True).stdout.strip())
        do_lease(pid, "alice", now_ms=1000)
        assert _lease_count() >= 1
        (pd / "a.json").unlink()
        _provision(pd)                                   # pool gone -> its leases gone
        assert _lease_count() == 0

    def test_leaves_other_pools_untouched(self, tmp_path):
        """Provisioning changes only the altered pool and leaves the others untouched."""
        pd = tmp_path / "pools.d"
        pd.mkdir()
        _pool_file(pd, "a.json", "10.55.0.0/24", 3600)
        _pool_file(pd, "b.json", "10.56.0.0/24", 600)
        _provision(pd)
        _pool_file(pd, "a.json", "10.55.0.0/24", 1200)   # change only a
        _provision(pd)
        p = _scratch_pools()
        assert p["10.55.0.0/24"] == "1200" and p["10.56.0.0/24"] == "600"


class TestBackupIntegrity:
    """Backups carry a checksum, are retained to a bounded count, and a restore
    verifies the checksum before touching the live database."""

    def _sha(self, path):
        return subprocess.run(["sha256sum", path], capture_output=True, text=True).stdout.split()[0]

    def test_backup_writes_matching_checksum(self, tmp_path):
        """A backup writes a checksum sidecar matching the dump's digest."""
        new_pool(lease_secs=1000)
        env = {**os.environ, "DHCPD_BACKUP_DIR": str(tmp_path)}
        path = subprocess.run(["dhcpd-backup"], capture_output=True, text=True,
                              env=env, check=True).stdout.strip()
        assert os.path.isfile(path + ".sha256")
        assert open(path + ".sha256").read().strip() == self._sha(path)

    def test_backup_retention_bounds_snapshots(self, tmp_path):
        """Backup retention keeps only DHCPD_BACKUP_KEEP snapshots."""
        new_pool(lease_secs=1000)
        env = {**os.environ, "DHCPD_BACKUP_DIR": str(tmp_path), "DHCPD_BACKUP_KEEP": "3"}
        for _ in range(6):
            subprocess.run(["dhcpd-backup"], capture_output=True, text=True, env=env, check=True)
        dumps = [f for f in os.listdir(tmp_path) if f.endswith(".sql")]
        assert len(dumps) == 3, dumps

    def test_restore_refuses_tampered_backup(self, tmp_path):
        """A restore refuses a tampered backup and leaves the database unchanged."""
        pid, _ = new_pool(lease_secs=1000)
        do_lease(pid, "alice", now_ms=1000)
        env = {**os.environ, "DHCPD_BACKUP_DIR": str(tmp_path)}
        path = subprocess.run(["dhcpd-backup"], capture_output=True, text=True,
                              env=env, check=True).stdout.strip()
        with open(path, "a") as f:
            f.write("\n-- tampered\n")                    # checksum no longer matches
        before = call({"op": "status", "pool_id": pid, "now_ms": 1000}).body["active"]
        r = subprocess.run(["dhcpd-restore", path], capture_output=True, text=True)
        assert r.returncode != 0                          # refused
        after = call({"op": "status", "pool_id": pid, "now_ms": 1000}).body["active"]
        assert after == before                            # database left unchanged

    def test_verified_restore_round_trips(self, tmp_path):
        """A verified restore round-trips lease state from a good backup."""
        pid, _ = new_pool(lease_secs=1000)
        ip = do_lease(pid, "alice", now_ms=1000).body["ip"]
        env = {**os.environ, "DHCPD_BACKUP_DIR": str(tmp_path)}
        path = subprocess.run(["dhcpd-backup"], capture_output=True, text=True,
                              env=env, check=True).stdout.strip()
        subprocess.run(["sqlite3", os.environ["DHCPD_DB"], "DELETE FROM leases;"], check=True)
        subprocess.run(["dhcpd-restore", path], check=True, capture_output=True, text=True)
        s = call({"op": "status", "pool_id": pid, "now_ms": 1000}).body
        assert s["active"] == 1 and [x["ip"] for x in s["leases"]] == [ip]


# ======================================================================= #
# Hardening: WAL state, config + integrity validators, overlap rejection,
# drift detection, concurrency-safe provisioning, admin audit trail,
# pre-restore safety snapshots, least-privilege state, and resource limits.
# ======================================================================= #
class TestHardening:
    def test_state_db_in_wal_mode(self):
        """The live state database runs in write-ahead-logging mode."""
        out = subprocess.run(["sqlite3", LIVE_DB, "PRAGMA journal_mode;"],
                             capture_output=True, text=True)
        assert out.stdout.strip().lower() == "wal", out.stdout

    def test_resource_limits_declared(self):
        """Resource limits for the service account are declared under limits.d."""
        path = "/etc/security/limits.d/dhcpd.conf"
        assert os.path.isfile(path)
        text = open(path).read()
        assert re.search(r"^\s*dhcpd\s+\w+\s+nofile\s+\d+", text, re.M), "nofile limit not declared"
        assert re.search(r"^\s*dhcpd\s+\w+\s+nproc\s+\d+", text, re.M), "nproc limit not declared"

    def test_state_tree_has_no_world_access(self):
        """Nothing under the state tree is accessible by other users."""
        for root, dirs, files in os.walk("/var/lib/dhcpd"):
            for name in dirs + files:
                p = os.path.join(root, name)
                if os.path.islink(p):
                    continue
                m = _mode(p)
                assert m & 0o007 == 0, (p, oct(m))

    def test_config_check_passes_and_flags_bad_pool(self, tmp_path):
        """dhcpd-check validates the config and every declared pool; a malformed
        pool (bad CIDR / non-positive lease) is rejected with a non-zero exit."""
        pd = tmp_path / "pools.d"
        pd.mkdir()
        _pool_file(pd, "ok.json", "10.62.0.0/24", 3600)
        env = {**os.environ, "DHCPD_POOLS_DIR": str(pd)}
        assert subprocess.run(["dhcpd-check"], env=env, capture_output=True).returncode == 0
        (pd / "bad.json").write_text('{"op":"create_pool","cidr":"nonsense","lease_secs":-5}')
        r = subprocess.run(["dhcpd-check"], env=env, capture_output=True)
        assert r.returncode != 0, "dhcpd-check must reject an invalid pool"

    def test_fsck_passes_healthy_and_fails_corrupt(self, tmp_path):
        """dhcpd-fsck passes a sound database and fails a corrupt one."""
        new_pool()
        assert subprocess.run(["dhcpd-fsck"], capture_output=True).returncode == 0
        bad = tmp_path / "corrupt.db"
        bad.write_bytes(b"this is definitely not a sqlite database file" * 8)
        r = subprocess.run(["dhcpd-fsck"], capture_output=True,
                           env={**os.environ, "DHCPD_DB": str(bad)})
        assert r.returncode != 0, "fsck must fail on a corrupt database"

    def test_provision_rejects_overlapping_cidr(self, tmp_path):
        """A declared pool that overlaps a pool already present is refused (non-zero
        exit) and not created; the existing pool is left intact."""
        pd = tmp_path / "pools.d"
        pd.mkdir()
        _pool_file(pd, "a.json", "10.60.0.0/24", 3600)
        _provision(pd)
        _pool_file(pd, "b.json", "10.60.0.128/25", 600)   # subset of the /24 -> overlaps
        r = subprocess.run(["dhcpd-provision"], capture_output=True, text=True,
                           env={**os.environ, "DHCPD_POOLS_DIR": str(pd)})
        assert r.returncode != 0, "an overlapping pool must be refused"
        assert _pool_rows("10.60.0.128/25") == 0, "the overlapping pool must not be created"
        assert _pool_rows("10.60.0.0/24") == 1, "the existing pool must remain"

    def test_provision_check_detects_drift_without_mutating(self, tmp_path):
        """dhcpd-provision --check exits 0 when the live pools match the declared set
        and non-zero on drift, without changing anything."""
        pd = tmp_path / "pools.d"
        pd.mkdir()
        _pool_file(pd, "a.json", "10.61.0.0/24", 3600)
        _provision(pd)
        env = {**os.environ, "DHCPD_POOLS_DIR": str(pd)}
        assert subprocess.run(["dhcpd-provision", "--check"], env=env,
                              capture_output=True).returncode == 0
        subprocess.run(["sqlite3", os.environ["DHCPD_DB"],
                        "DELETE FROM pools WHERE cidr='10.61.0.0/24';"], check=True)
        r = subprocess.run(["dhcpd-provision", "--check"], env=env, capture_output=True)
        assert r.returncode != 0, "--check must report drift"
        assert _pool_rows("10.61.0.0/24") == 0, "--check must not mutate the database"

    def test_provision_is_concurrency_safe(self, tmp_path):
        """Concurrent provisions serialise (lock) and never duplicate a pool."""
        pd = tmp_path / "pools.d"
        pd.mkdir()
        _pool_file(pd, "a.json", "10.63.0.0/24", 3600)
        env = {**os.environ, "DHCPD_POOLS_DIR": str(pd)}
        procs = [subprocess.Popen(["dhcpd-provision"], env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                 for _ in range(4)]
        codes = [p.wait() for p in procs]
        assert all(c == 0 for c in codes), codes
        assert _pool_rows("10.63.0.0/24") == 1, "concurrent provisions must not duplicate a pool"

    def test_admin_actions_are_audited(self, tmp_path):
        """Mutating maintenance commands append to a private, service-owned audit log."""
        env = {**os.environ, "DHCPD_BACKUP_DIR": str(tmp_path)}
        subprocess.run(["dhcpd-backup"], env=env, check=True, capture_output=True)
        log = "/var/log/dhcpd/admin.log"
        assert os.path.isfile(log)
        assert _stat_owner(log) == ("dhcpd", "dhcpd")
        assert _mode(log) == 0o640
        assert "dhcpd-backup" in open(log).read()

    def test_restore_takes_checksummed_pre_restore_snapshot(self, tmp_path):
        """Restore snapshots the current database before overwriting it, and that
        safety snapshot itself carries a matching checksum, so a mistaken restore
        can be rolled back and its snapshot verified."""
        pid, _ = new_pool(lease_secs=1000)
        do_lease(pid, "alice", now_ms=1000)
        env = {**os.environ, "DHCPD_BACKUP_DIR": str(tmp_path)}
        path = subprocess.run(["dhcpd-backup"], env=env, check=True,
                              capture_output=True, text=True).stdout.strip()
        subprocess.run(["dhcpd-restore", path], env=env, check=True, capture_output=True)
        snaps = glob.glob(str(tmp_path / "pre-restore-*.sql"))
        assert snaps, "restore must write a pre-restore safety snapshot"
        snap = snaps[0]
        assert os.path.isfile(snap + ".sha256"), "pre-restore snapshot must be checksummed"
        got = subprocess.run(["sha256sum", snap], capture_output=True, text=True).stdout.split()[0]
        assert open(snap + ".sha256").read().strip() == got

    def test_provision_validates_before_applying(self, tmp_path):
        """A single malformed pool declaration aborts the whole provision with no
        partial changes: the valid pools in the same directory are not created."""
        pd = tmp_path / "pools.d"
        pd.mkdir()
        _pool_file(pd, "good.json", "10.64.0.0/24", 3600)
        (pd / "bad.json").write_text('{"op":"create_pool","cidr":"garbage","lease_secs":0}')
        r = subprocess.run(["dhcpd-provision"], capture_output=True, text=True,
                           env={**os.environ, "DHCPD_POOLS_DIR": str(pd)})
        assert r.returncode != 0, "a malformed pool file must abort provisioning"
        assert _pool_rows("10.64.0.0/24") == 0, "no pool may be created when a declaration is invalid"


# ======================================================================= #
# Advanced maintenance: transactional pool renumbering with state re-homing,
# a cross-table consistency audit, an HMAC-signed state attestation, and
# least-privilege operator delegation through sudo.
# ======================================================================= #
def _scratch(sql):
    """Run a query against the throwaway DHCPD_DB and return stripped stdout."""
    return subprocess.run(["sqlite3", os.environ["DHCPD_DB"], sql],
                          capture_output=True, text=True).stdout.strip()


class TestPoolRenumber:
    """dhcpd-renumber moves a pool to a new range in one transaction, re-homing
    every reservation, lease, and decline by its offset from the network address
    and dropping what no longer fits, and refuses to overlap another pool."""

    def test_advanced_commands_installed(self):
        """The renumber, audit, and verify commands are installed on PATH."""
        for c in ("dhcpd-renumber", "dhcpd-audit", "dhcpd-verify"):
            p = shutil.which(c)
            assert p is not None and os.access(p, os.X_OK), c

    def test_renumber_rehomes_state_by_offset(self):
        """Renumbering to a same-size range moves the pool and shifts its leases and
        reservations by the same offset from the network address."""
        pid, base = new_pool(prefix=24, reservations=[(10, "printer")])
        do_lease(pid, "alice", now_ms=1000)      # base.1
        do_lease(pid, "bob", now_ms=1000)        # base.2
        n = next(_net)
        nb = f"10.{n}.0"
        r = subprocess.run(["dhcpd-renumber", f"{base}.0/24", f"{nb}.0/24"],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert _scratch(f"SELECT cidr FROM pools WHERE id={pid};") == f"{nb}.0/24"
        ips = sorted(int(x) for x in _scratch(f"SELECT ip FROM leases WHERE pool_id={pid};").split())
        assert ips == [_ip_to_int(f"{nb}.1"), _ip_to_int(f"{nb}.2")]
        assert int(_scratch(
            f"SELECT ip FROM reservations WHERE pool_id={pid} AND client_id='printer';"
        )) == _ip_to_int(f"{nb}.10")

    def test_renumber_shrink_drops_out_of_range(self):
        """Renumbering into a smaller range drops the addresses that no longer fit and
        re-homes the ones that do."""
        pid, base = new_pool(prefix=24)
        do_lease(pid, "alice", now_ms=1000)                                 # base.1
        assert do_lease(pid, "hi", requested_ip=f"{base}.200", now_ms=1000).body["ip"] == f"{base}.200"
        n = next(_net)
        nb = f"10.{n}.0"
        r = subprocess.run(["dhcpd-renumber", f"{base}.0/24", f"{nb}.0/26"],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        ips = sorted(int(x) for x in _scratch(f"SELECT ip FROM leases WHERE pool_id={pid};").split())
        assert ips == [_ip_to_int(f"{nb}.1")], "the .200 lease is outside the /26 and must be dropped"

    def test_renumber_refuses_overlap_and_leaves_state(self):
        """Renumbering onto a range that overlaps a different pool is refused and
        changes nothing."""
        pid_a, base_a = new_pool(prefix=24)
        pid_b, base_b = new_pool(prefix=24)
        r = subprocess.run(["dhcpd-renumber", f"{base_a}.0/24", f"{base_b}.0/24"],
                           capture_output=True, text=True)
        assert r.returncode != 0, "an overlapping renumber must be refused"
        assert _scratch(f"SELECT cidr FROM pools WHERE id={pid_a};") == f"{base_a}.0/24"
        assert _scratch(f"SELECT cidr FROM pools WHERE id={pid_b};") == f"{base_b}.0/24"

    def test_renumber_unknown_pool_fails(self):
        """Renumbering a pool that is not present fails without creating anything."""
        r = subprocess.run(["dhcpd-renumber", "10.222.0.0/24", "10.223.0.0/24"],
                           capture_output=True, text=True)
        assert r.returncode != 0
        assert _pool_rows("10.223.0.0/24") == 0


class TestConsistencyAudit:
    """dhcpd-audit reconciles leases, reservations, and declines against pool ranges."""

    def test_audit_clean_passes_strict(self):
        """A consistent database passes the strict audit."""
        pid, _ = new_pool(prefix=29)
        do_lease(pid, "alice", now_ms=1000)
        r = subprocess.run(["dhcpd-audit", "--strict"], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr

    def test_audit_flags_out_of_range_lease(self):
        """A lease outside the pool usable range is counted and fails the strict audit."""
        pid, base = new_pool(prefix=29)                      # usable base.1 .. base.6
        bcast = _ip_to_int(f"{base}.7")                      # broadcast: out of range
        subprocess.run(["sqlite3", os.environ["DHCPD_DB"],
                        f"INSERT INTO leases(ip,pool_id,client_id,expires_ms,created_ms,state) "
                        f"VALUES({bcast},{pid},'ghost',9,0,'active');"], check=True)
        r = subprocess.run(["dhcpd-audit", "--strict"], capture_output=True, text=True)
        assert r.returncode != 0, "the strict audit must fail on an inconsistency"
        rows = [json.loads(x) for x in r.stdout.splitlines() if x.strip()]
        pool_row = next(x for x in rows if x.get("pool_id") == pid)
        assert pool_row["lease_out_of_range"] >= 1
        assert rows[-1]["inconsistencies"] >= 1


class TestStateAttestation:
    """dhcpd-verify prints a canonical HMAC-signed manifest of the database state."""

    @staticmethod
    def _expected(db):
        def q(sql):
            return subprocess.run(["sqlite3", db, sql], capture_output=True, text=True).stdout.splitlines()
        lines = []
        lines += q("SELECT 'POOL '||cidr||' '||lease_secs FROM pools ORDER BY network;")
        lines += q("SELECT 'RESV '||p.cidr||' '||r.ip||' '||CASE WHEN r.client_id='' THEN '-' ELSE r.client_id END "
                   "FROM reservations r JOIN pools p ON p.id=r.pool_id ORDER BY p.network, r.ip, r.client_id;")
        lines += q("SELECT 'LEASE '||p.cidr||' '||l.ip||' '||l.client_id||' '||l.expires_ms||' '||l.state "
                   "FROM leases l JOIN pools p ON p.id=l.pool_id ORDER BY p.network, l.ip;")
        lines += q("SELECT 'DECLINE '||p.cidr||' '||d.ip FROM declines d JOIN pools p ON p.id=d.pool_id "
                   "ORDER BY p.network, d.ip;")
        msg = "".join(ln + "\n" for ln in lines).encode()
        key = hashlib.sha256(b"dhcpd-verify-v1").digest()
        return lines, hmac.new(key, msg, hashlib.sha256).hexdigest()

    def test_verify_manifest_and_tag_match_independent_recompute(self):
        """The manifest lines and the HMAC-SHA256 tag match an independent
        reconstruction of the database state byte for byte."""
        pid1, b1 = new_pool(prefix=24, reserved_offsets=[1], reservations=[(10, "printer")])
        do_lease(pid1, "alice", now_ms=1000)
        do_lease(pid1, "bob", now_ms=1000)
        do_decline(f"{b1}.5")
        new_pool(prefix=28)
        out = subprocess.run(["dhcpd-verify"], capture_output=True, text=True, check=True).stdout.splitlines()
        assert out[-1].startswith("TAG ")
        got_lines, got_tag = out[:-1], out[-1].split()[1]
        exp_lines, exp_tag = self._expected(os.environ["DHCPD_DB"])
        assert got_lines == exp_lines, (got_lines, exp_lines)
        assert got_tag == exp_tag

    def test_verify_binds_state_changes(self):
        """The signed tag changes after a renumber and matches the recomputed post-state,
        so the attestation binds the renumber's correctness."""
        pid, base = new_pool(prefix=24)
        do_lease(pid, "alice", now_ms=1000)
        before = subprocess.run(["dhcpd-verify"], capture_output=True, text=True, check=True).stdout.splitlines()[-1]
        n = next(_net)
        nb = f"10.{n}.0"
        subprocess.run(["dhcpd-renumber", f"{base}.0/24", f"{nb}.0/24"], check=True, capture_output=True, text=True)
        after = subprocess.run(["dhcpd-verify"], capture_output=True, text=True, check=True).stdout.splitlines()
        assert after[-1] != before, "the tag must change when the state changes"
        _lines, exp_tag = self._expected(os.environ["DHCPD_DB"])
        assert after[-1].split()[1] == exp_tag


class TestOperatorDelegation:
    """A least-privilege sudo policy delegates only the read-only maintenance
    commands to the dhcpdops operator group, as the service account."""

    def test_operator_group_exists(self):
        """The dhcpdops operator group exists."""
        grp.getgrnam("dhcpdops")

    def test_sudoers_policy_is_scoped_and_valid(self):
        """A sudoers drop-in under /etc/sudoers.d (any filename, per the spec) parses cleanly, is mode
        0440, and delegates to %dhcpdops as the dhcpd account, password-less, exactly the read-only
        commands - dhcpd-report, dhcpd-verify, dhcpd-audit, dhcpd-fsck, dhcpd-check, and dhcpd-provision
        only with the --check flag - and none of the state-changing commands (dhcpd-backup, dhcpd-restore,
        dhcpd-reap, dhcpd-renumber), no unqualified dhcpd-provision, and no blanket grant."""
        # The spec fixes the directory, not the filename: find the file(s) that grant the group.
        candidates = []
        for path in sorted(glob.glob("/etc/sudoers.d/*")):
            if not os.path.isfile(path):
                continue
            try:
                lines = open(path).read().splitlines()
            except OSError:
                continue
            if any("%dhcpdops" in ln for ln in lines if ln.strip() and not ln.strip().startswith("#")):
                candidates.append(path)
        assert candidates, "no sudoers policy file under /etc/sudoers.d delegates to %dhcpdops"
        grant_lines = []
        for path in candidates:
            assert _mode(path) == 0o440, (path, oct(_mode(path)))
            assert subprocess.run(["visudo", "-cf", path], capture_output=True).returncode == 0, path
            grant_lines += [ln for ln in open(path).read().splitlines()
                            if ln.strip() and not ln.strip().startswith("#") and "%dhcpdops" in ln]
        grant = "\n".join(grant_lines)
        assert re.search(r"\(\s*dhcpd\b", grant), "commands must run as the dhcpd account"
        assert re.search(r"\bNOPASSWD\b", grant), "the delegation must be password-less"
        assert not re.search(r"NOPASSWD\s*:\s*ALL\b", grant), "must not grant all commands"
        # Parse each grant line's command list (everything after the tag colon).
        by_cmd = {}
        for ln in grant_lines:
            if ":" not in ln:
                continue
            for entry in ln.rsplit(":", 1)[1].split(","):
                toks = entry.split()
                if toks:
                    by_cmd.setdefault(os.path.basename(toks[0]), []).append(toks[1:])
        for cmd in ("dhcpd-report", "dhcpd-verify", "dhcpd-audit", "dhcpd-fsck", "dhcpd-check"):
            assert cmd in by_cmd, f"{cmd} must be delegated"
        assert "dhcpd-provision" in by_cmd, "dhcpd-provision --check must be delegated"
        assert all("--check" in args for args in by_cmd["dhcpd-provision"]), \
            "dhcpd-provision must be delegated only with the --check flag, never unqualified"
        for forbidden in ("dhcpd-backup", "dhcpd-restore", "dhcpd-reap", "dhcpd-renumber"):
            assert forbidden not in by_cmd, f"{forbidden} must not be delegated"
