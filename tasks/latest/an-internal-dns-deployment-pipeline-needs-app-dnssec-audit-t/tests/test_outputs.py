import copy
import json
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def cases(tmp_path_factory):
    """Generate fresh signed bundles without exposing private material to the task repo."""
    out = tmp_path_factory.mktemp("vectors") / "cases.json"
    subprocess.run(["go", "run", "/tests/genfixtures.go", str(out)], check=True, timeout=60)
    return json.loads(out.read_text())


def run_bundle(bundle, *, stdin=True):
    """Run the submitted security gate through either supported input mode."""
    subprocess.run(["go", "build", "-o", "/app/dnssec-audit", "./cmd/dnssec-audit"], cwd="/app", check=True, timeout=60)
    raw = json.dumps(bundle)
    if stdin:
        proc = subprocess.run(["/app/dnssec-audit"], input=raw, text=True, capture_output=True, timeout=15)
    else:
        path = Path("/tmp/delegation.json")
        path.write_text(raw)
        proc = subprocess.run(["/app/dnssec-audit", str(path)], text=True, capture_output=True, timeout=15)
    assert proc.returncode == 0, proc.stderr
    value = json.loads(proc.stdout)
    assert set(value) == {"admit", "reasons"}
    assert value["reasons"] == sorted(set(value["reasons"]))
    return value


@pytest.mark.parametrize("name", ["valid", "casefold", "wildcard"])
def test_accepts_authenticated_delegations(cases, name):
    """Validates DS binding, canonical sorting, case folding, and wildcard label handling."""
    assert run_bundle(cases[name]) == {"admit": True, "reasons": []}


def test_file_argument_matches_stdin(cases):
    """The documented file and stdin interfaces produce the same admission decision."""
    assert run_bundle(cases["casefold"], stdin=False) == run_bundle(cases["casefold"])


@pytest.mark.parametrize("change", ["digest", "flags", "protocol", "algorithm"])
def test_rejects_unauthenticated_dnskeys(cases, change):
    """A parent DS must authenticate an eligible supported child key."""
    b = copy.deepcopy(cases["valid"])
    if change == "digest":
        b["parent_ds"][0]["digest"] = "00" * 32
    elif change == "flags":
        b["dnskeys"][0]["flags"] = 256
    elif change == "protocol":
        b["dnskeys"][0]["protocol"] = 2
    else:
        b["parent_ds"][0]["algorithm"] = 13
    out = run_bundle(b)
    assert not out["admit"] and "no_ds_match" in out["reasons"]


@pytest.mark.parametrize("field,value", [("inception", 1800000000), ("expiration", 1600000000), ("signer", "other.test."), ("labels", 0), ("original_ttl", 42), ("type_covered", 1)])
def test_signature_policy_boundaries(cases, field, value):
    """Expired, premature, mis-scoped, and structurally mismatched signatures are refused."""
    b = copy.deepcopy(cases["valid"])
    b["rrsets"][0]["signatures"][0][field] = value
    out = run_bundle(b)
    assert not out["admit"] and "bad_signature" in out["reasons"]


@pytest.mark.parametrize("mutation,reason", [("owner", "bad_name"), ("outside", "bad_rrset"), ("empty", "bad_rrset"), ("rdata", "malformed_key"), ("signature", "malformed_key")])
def test_malformed_and_out_of_zone_data(cases, mutation, reason):
    """Malformed encodings and records outside the delegated zone fail safely."""
    b = copy.deepcopy(cases["valid"])
    if mutation == "owner":
        b["rrsets"][0]["owner"] = "relative"
    elif mutation == "outside":
        b["rrsets"][0]["owner"] = "www.evil.test."
    elif mutation == "empty":
        b["rrsets"][0]["records"] = []
    elif mutation == "rdata":
        b["rrsets"][0]["records"] = ["%%%"]
    else:
        b["rrsets"][0]["signatures"][0]["signature"] = "%%%"
    out = run_bundle(b)
    assert not out["admit"] and reason in out["reasons"]


def test_invalid_json_is_a_clean_rejection():
    """A structurally invalid request is rejected without panic or traceback."""
    proc = subprocess.run(["/app/dnssec-audit"], input="{broken", text=True, capture_output=True, timeout=15)
    assert proc.returncode == 0 and proc.stderr == ""
    assert json.loads(proc.stdout) == {"admit": False, "reasons": ["invalid_input"]}


@pytest.mark.parametrize(
    "raw",
    [
        '{"now":1,"now":2,"zone":"example.test.","parent_ds":[],"dnskeys":[],"rrsets":[]}',
        '{"now":1,"zone":"example.test.","parent_ds":[],"dnskeys":[],"rrsets":[],"rrsets":[]}',
        '{"now":1,"zone":"example.test.","parent_ds":[],"dnskeys":[],"rrsets":[],"extra":0}',
        '{"now":1,"zone":"example.test.","parent_ds":[],"dnskeys":[]}',
        '{"now":1,"zone":"example.test.","parent_ds":[],"dnskeys":[],"rrsets":null}',
        '{"now":1,"zone":"example.test.","parent_ds":[],"dnskeys":[],"rrsets":[]} {}',
    ],
)
def test_json_object_boundary_is_strict(raw):
    """Ambiguous, incomplete, null, and trailing members are structural errors."""
    proc = subprocess.run(
        ["/app/dnssec-audit"], input=raw, text=True, capture_output=True, timeout=15
    )
    assert proc.returncode == 0 and proc.stderr == ""
    assert json.loads(proc.stdout) == {"admit": False, "reasons": ["invalid_input"]}
