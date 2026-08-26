import hashlib
import os
import signal
import subprocess
import time
from pathlib import Path

import pytest


APP = Path(os.environ.get("APP_ROOT", "/app"))
CONF = APP / "live/named.conf"
KEY = APP / "live/keys/harbor-ops.key"
PORT = "5300"
INTERNAL = "127.0.0.1"
EXTERNAL = "127.0.0.2"
SERVER = "127.0.0.1"

EVIDENCE_HASHES = {
    "external.records": "9857a0e213283e22fdf995a119df32797dbc854d656ec375ec76a00693c0eea6",
    "harbor-ops.secret": "1d72e86e21e45c4253b26d39664b39b94fd7b91883a8956425f8c0f087aac1a5",
    "internal.records": "315d5f7ca3aa0bdd60d7cbbd88168b5a6b8ce00777e69c27e5d78b51982ca1e9",
    "recovery-policy.txt": "a855249dbfcc1bbc31cab0f75310f168967670e5ede2629f51b902e59da9326a",
}


def command(args, *, input_text=None, timeout=15):
    return subprocess.run(args, input=input_text, text=True, capture_output=True, timeout=timeout)


def dig(source, name, rtype="A", *extra):
    return command(["dig", "-b", source, f"@{SERVER}", "-p", PORT, name, rtype, "+noall", "+answer", "+comments", *extra])


def answer_lines(result):
    return [line for line in result.stdout.splitlines() if line and not line.startswith(";")]


def status(result):
    marker = "status: "
    start = result.stdout.find(marker)
    assert start >= 0, result.stdout + result.stderr
    return result.stdout[start + len(marker):].split(",", 1)[0]


def start_named():
    checked = command(["named-checkconf", "-z", str(CONF)])
    assert checked.returncode == 0, checked.stdout + checked.stderr
    proc = subprocess.Popen(
        ["named", "-c", str(CONF), "-g", "-u", "root"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        for _ in range(80):
            probe = dig(EXTERNAL, "harbor.test", "SOA")
            if probe.returncode == 0 and status(probe) == "NOERROR" and answer_lines(probe):
                break
            if proc.poll() is not None:
                output = proc.stdout.read() if proc.stdout else ""
                pytest.fail(f"named exited during startup:\n{output}")
            time.sleep(0.1)
        else:
            pytest.fail("named did not become authoritative on port 5300")
        return proc
    except BaseException:
        if proc.poll() is None:
            proc.kill()
        raise


def stop_named(proc):
    if proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


@pytest.fixture(scope="module", autouse=True)
def named_service():
    state = {"proc": start_named()}
    try:
        yield state
    finally:
        stop_named(state["proc"])


def test_01_evidence_integrity_and_sorted_custody_manifest():
    evidence = APP / "evidence"
    assert sorted(p.name for p in evidence.iterdir() if p.is_file()) == sorted(EVIDENCE_HASHES)
    for name, expected in EVIDENCE_HASHES.items():
        assert hashlib.sha256((evidence / name).read_bytes()).hexdigest() == expected
    expected_lines = [f"{EVIDENCE_HASHES[n]}  /app/evidence/{n}" for n in sorted(EVIDENCE_HASHES)]
    assert (APP / "recovery/evidence.sha256").read_text().splitlines() == expected_lines


def test_02_exact_change_manifest_and_restart_safe_tree():
    expected = (
        "artifact\tview\trole\n"
        "/app/live/zones/external.harbor.test.zone\texternal\tforward-primary\n"
        "/app/live/zones/external.192.0.2.zone\texternal\treverse-primary\n"
        "/app/live/zones/internal.harbor.test.zone\tinternal\tforward-primary-dynamic\n"
        "/app/live/zones/internal.192.0.2.zone\tinternal\treverse-primary\n"
        "/app/live/zones/internal.rpz\tinternal\tresponse-policy\n"
    )
    assert (APP / "recovery/changes.tsv").read_text() == expected
    for rel in ["live/named.conf", "live/keys/harbor-ops.key", "live/run", "live/zones"]:
        assert (APP / rel).exists()


def test_03_configuration_and_all_master_zones_validate():
    assert command(["named-checkconf", str(CONF)]).returncode == 0
    zones = {
        "harbor.test": ["external.harbor.test.zone", "internal.harbor.test.zone"],
        "2.0.192.in-addr.arpa": ["external.192.0.2.zone", "internal.192.0.2.zone"],
        "internal.rpz": ["internal.rpz"],
    }
    for origin, files in zones.items():
        for name in files:
            result = command(["named-checkzone", origin, str(APP / "live/zones" / name)])
            assert result.returncode == 0, result.stdout + result.stderr
    assert (APP / "live/run/named.pid").exists()
    version = command(["dig", "-b", EXTERNAL, f"@{SERVER}", "-p", PORT, "version.bind", "TXT", "CH", "+short"])
    assert "9.18" not in version.stdout and "BIND" not in version.stdout


def test_04_destination_views_are_isolated_and_authoritative():
    ext = dig(EXTERNAL, "www.harbor.test", "A")
    internal = dig(INTERNAL, "www.harbor.test", "A")
    assert "192.0.2.80" in ext.stdout and "10.24.8.80" not in ext.stdout
    assert "10.24.8.80" in internal.stdout and "192.0.2.80" not in internal.stdout
    assert status(dig(EXTERNAL, "db.harbor.test", "A")) == "NXDOMAIN"
    assert "10.24.9.40" in dig(INTERNAL, "db.harbor.test", "A").stdout


def test_05_forward_records_ttls_aliases_wildcard_and_serials():
    assert "120" in answer_lines(dig(EXTERNAL, "api.harbor.test", "CNAME"))[0]
    assert "www.harbor.test." in dig(EXTERNAL, "api.harbor.test", "CNAME").stdout
    assert "192.0.2.90" in dig(EXTERNAL, "blue.preview.harbor.test", "A").stdout
    assert "10.24.8.90" in dig(INTERNAL, "blue.preview.harbor.test", "A").stdout
    assert "2001:db8:0:80::1" in dig(EXTERNAL, "www.harbor.test", "AAAA").stdout
    assert "2001:db8:24:8::80" in dig(INTERNAL, "www.harbor.test", "AAAA").stdout
    assert "10 mail.harbor.test." in dig(EXTERNAL, "harbor.test", "MX").stdout
    assert '"public green"' in dig(EXTERNAL, "status.harbor.test", "TXT").stdout
    assert '"internal amber"' in dig(INTERNAL, "status.harbor.test", "TXT").stdout
    assert "192.0.2.53" in dig(EXTERNAL, "ns1.harbor.test", "A").stdout
    assert "10.24.0.53" in dig(INTERNAL, "ns1.harbor.test", "A").stdout
    for addr in (EXTERNAL, INTERNAL):
        soa = dig(addr, "harbor.test", "SOA").stdout
        assert "2026071607 900 300 604800 60" in " ".join(soa.split())


def test_06_delegation_and_view_local_glue_are_preserved():
    for addr, glue in ((EXTERNAL, "192.0.2.54"), (INTERNAL, "10.24.0.54")):
        ns = dig(addr, "apps.harbor.test", "NS", "+norecurse", "+authority", "+additional")
        assert "ns.apps.harbor.test." in ns.stdout
        assert glue in ns.stdout


def test_07_reverse_views_have_exact_approved_ptr_set():
    expected = {"25": "mail.harbor.test.", "53": "ns1.harbor.test.", "54": "ns.apps.harbor.test.", "80": "www.harbor.test."}
    for addr in (EXTERNAL, INTERNAL):
        for octet, target in expected.items():
            assert target in dig(addr, f"{octet}.2.0.192.in-addr.arpa", "PTR").stdout
        assert status(dig(addr, "81.2.0.192.in-addr.arpa", "PTR")) == "NXDOMAIN"


def test_08_rpz_blocks_only_internal_and_preserves_exception():
    assert status(dig(INTERNAL, "malware.example", "A")) == "NXDOMAIN"
    assert status(dig(INTERNAL, "x.exfil.example", "A")) == "NXDOMAIN"
    rpz_dump = command(["named-checkzone", "-D", "internal.rpz", str(APP / "live/zones/internal.rpz")])
    assert "safe.exfil.example.internal.rpz." in rpz_dump.stdout
    assert "CNAME\trpz-passthru." in rpz_dump.stdout
    assert status(dig(EXTERNAL, "malware.example", "A")) == "REFUSED"
    assert (APP / "live/run/rpz.log").exists()


def test_09_tsig_transfer_boundary_matches_views_and_zones():
    internal = command(["dig", "-b", INTERNAL, "-k", str(KEY), f"@{SERVER}", "-p", PORT, "harbor.test", "AXFR"])
    external = command(["dig", "-b", EXTERNAL, "-k", str(KEY), f"@{SERVER}", "-p", PORT, "harbor.test", "AXFR"])
    external_reverse = command(["dig", "-b", EXTERNAL, "-k", str(KEY), f"@{SERVER}", "-p", PORT, "2.0.192.in-addr.arpa", "AXFR"])
    reverse = command(["dig", "-b", INTERNAL, "-k", str(KEY), f"@{SERVER}", "-p", PORT, "2.0.192.in-addr.arpa", "AXFR"])
    assert internal.returncode == 0 and "2026071607" in internal.stdout
    assert reverse.returncode == 0 and "ns1.harbor.test." in reverse.stdout
    assert external.returncode != 0 or "Transfer failed" in external.stdout + external.stderr
    assert external_reverse.returncode != 0 or "Transfer failed" in external_reverse.stdout + external_reverse.stderr


def nsupdate(commands, source=INTERNAL):
    return command(["nsupdate", "-k", str(KEY)], input_text=f"local {source}\nserver {SERVER} {PORT}\n{commands}\nsend\n")


def test_10_authenticated_update_is_scoped_and_survives_restart(named_service):
    allowed = nsupdate("zone harbor.test.\nupdate add blue.dynamic.harbor.test. 60 A 10.24.30.7")
    assert allowed.returncode == 0, allowed.stdout + allowed.stderr
    assert "10.24.30.7" in dig(INTERNAL, "blue.dynamic.harbor.test", "A").stdout
    assert status(dig(EXTERNAL, "blue.dynamic.harbor.test", "A")) == "NXDOMAIN"
    journal = APP / "live/zones/internal.harbor.test.zone.jnl"
    assert journal.is_file() and journal.stat().st_size > 0

    stop_named(named_service["proc"])
    named_service["proc"] = start_named()
    assert "10.24.30.7" in dig(INTERNAL, "blue.dynamic.harbor.test", "A").stdout
    assert status(dig(EXTERNAL, "blue.dynamic.harbor.test", "A")) == "NXDOMAIN"

    for update in [
        "update add dynamic.harbor.test. 60 A 10.24.30.8",
        "update add blue.dynamic.harbor.test. 60 TXT \"forbidden\"",
        "update add sibling.harbor.test. 60 A 10.24.30.9",
    ]:
        result = nsupdate(f"zone harbor.test.\n{update}")
        assert result.returncode != 0 or "REFUSED" in result.stderr


def test_11_unauthenticated_updates_and_non_dynamic_zones_are_rejected():
    unsigned = command(["nsupdate"], input_text=f"local {INTERNAL}\nserver {SERVER} {PORT}\nzone harbor.test.\nupdate add red.dynamic.harbor.test. 60 A 10.24.30.10\nsend\n")
    reverse = nsupdate("zone 2.0.192.in-addr.arpa.\nupdate add 99.2.0.192.in-addr.arpa. 60 PTR rogue.harbor.test.")
    external_forward = nsupdate("zone harbor.test.\nupdate add rogue.harbor.test. 60 A 192.0.2.99", EXTERNAL)
    external_reverse = nsupdate("zone 2.0.192.in-addr.arpa.\nupdate add 99.2.0.192.in-addr.arpa. 60 PTR rogue.harbor.test.", EXTERNAL)
    assert unsigned.returncode != 0 or "REFUSED" in unsigned.stderr
    assert reverse.returncode != 0 or "REFUSED" in reverse.stderr
    assert external_forward.returncode != 0 or "REFUSED" in external_forward.stderr
    assert external_reverse.returncode != 0 or "REFUSED" in external_reverse.stderr
    assert not answer_lines(dig(INTERNAL, "red.dynamic.harbor.test", "A"))
    assert not answer_lines(dig(INTERNAL, "99.2.0.192.in-addr.arpa", "PTR"))
