"""End-to-end verification of the dispatch zone reconciliation service.

The verifier connects to Redis exactly as the task's redis.conf provisions it
(nonstandard port and password), seeds a fresh keyspace, and drives the service
through the reconcile client. It then checks the produced report and the live
Redis state against an expectation computed independently from the canonical
CSV, the seed, and the operator override archive. Because the verifier re-runs
the real pipeline from a fresh seed, a correct result can only come from a
correctly configured, working service, not from a pre-written report.
"""

import csv
import json
import subprocess
import tarfile
import time
import urllib.request
from pathlib import Path

import pytest
import redis

APP = Path("/app")
CSV_PATH = APP / "data" / "taxi_zone_lookup.csv"
SEED_PATH = APP / "data" / "zones.seed.json"
ARCHIVE_PATH = APP / "dispatch-config.tar.gz"
REPORT_PATH = APP / "output" / "reconciliation-report.json"
CLIENT = APP / "scripts" / "reconcile-client.js"
REDIS_CONF = APP / "config" / "redis.conf"
SERVICE_JSON = APP / "config" / "service.json"
SERVICE_ENV = APP / "config" / "service.overrides"

FIELDS = ["borough", "zone", "service_zone"]


# --------------------------------------------------------------------------- #
# Config discovery (how Redis and the service are actually provisioned)        #
# --------------------------------------------------------------------------- #
def redis_conn_params():
    """Read the live Redis port and password straight from redis.conf."""
    port, password = 6379, None
    for line in REDIS_CONF.read_text().splitlines():
        t = line.strip()
        if t.startswith("port "):
            port = int(t.split()[1])
        elif t.startswith("requirepass "):
            password = t.split(None, 1)[1].strip().strip('"').strip("'")
    return port, password


def _parse_env_file(path):
    out = {}
    for line in path.read_text().splitlines():
        t = line.strip()
        if not t or t.startswith("#") or "=" not in t:
            continue
        k, v = t.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def effective_http_port():
    """service.json base, overridden by service.overrides (matches src/config.js)."""
    cfg = json.loads(SERVICE_JSON.read_text())
    port = int(cfg.get("http", {}).get("port", 3000))
    if SERVICE_ENV.exists():
        env = _parse_env_file(SERVICE_ENV)
        if env.get("DISPATCH_HTTP_PORT"):
            port = int(env["DISPATCH_HTTP_PORT"])
    return port


# --------------------------------------------------------------------------- #
# Independent loaders / expectation                                           #
# --------------------------------------------------------------------------- #
def load_seed():
    return json.loads(SEED_PATH.read_text())["zones"]


def load_canonical():
    out = {}
    with CSV_PATH.open(newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                cid = int(row["LocationID"])
            except (TypeError, ValueError):
                continue
            out[cid] = {
                "borough": row["Borough"],
                "zone": row["Zone"],
                "service_zone": row["service_zone"],
            }
    return out


def load_overrides():
    with tarfile.open(ARCHIVE_PATH, "r:gz") as tf:
        member = tf.extractfile("./overrides.json") or tf.extractfile("overrides.json")
        return json.loads(member.read().decode("utf-8"))


def compute_expected():
    """Reference reconciliation derived only from the input files.

    Canonical TLC values overwrite drifted Redis fields; a locked operator
    override wins over canonical for the fields it names; unlocked overrides are
    ignored; LocationIDs absent from the canonical lookup are left untouched. The
    stored version increases by one when (and only when) a field changes.
    """
    seed = load_seed()
    canon = load_canonical()
    overrides = load_overrides()

    expected_state, expected_versions, changes = {}, {}, []
    reconciled = unchanged = locked = unknown = 0

    for z in seed:
        cid = z["location_id"]
        current = {f: z[f] for f in FIELDS}
        canon_row = canon.get(cid)

        if canon_row is None:
            expected_state[cid] = dict(current)
            expected_versions[cid] = z["version"]
            unknown += 1
            continue

        target = {f: canon_row[f] for f in FIELDS}
        applied = False
        ov = overrides.get(str(cid))
        if ov and ov.get("locked") is True:
            for f in FIELDS:
                if f in ov:
                    target[f] = ov[f]
            applied = True
        if applied:
            locked += 1

        changed = sorted([f for f in FIELDS if target[f] != current[f]])
        if changed:
            reason = "override_locked" if applied else "reconciled"
            if reason == "reconciled":
                reconciled += 1
            changes.append({"location_id": cid, "fields": changed, "reason": reason})
            expected_versions[cid] = z["version"] + 1
        else:
            unchanged += 1
            expected_versions[cid] = z["version"]
        expected_state[cid] = target

    changes.sort(key=lambda c: c["location_id"])
    report = {
        "generated_from": "redis",
        "total_zones": len(seed),
        "reconciled": reconciled,
        "unchanged": unchanged,
        "locked_overrides": locked,
        "unknown_zones": unknown,
        "changes": changes,
    }
    return report, expected_state, expected_versions


# --------------------------------------------------------------------------- #
# Harness helpers                                                             #
# --------------------------------------------------------------------------- #
def connect_redis():
    port, password = redis_conn_params()
    last = None
    for _ in range(50):
        try:
            r = redis.Redis(host="127.0.0.1", port=port, password=password, decode_responses=True)
            r.ping()
            return r
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(0.2)
    raise AssertionError(
        f"Redis is not reachable on 127.0.0.1:{port} with the configured password. "
        f"Is the data directory provisioned and the connection configured? ({last})"
    )


def wait_for_service(port):
    last = None
    for _ in range(75):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as resp:
                if resp.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(0.2)
    raise AssertionError(f"dispatch service never became healthy on port {port} ({last})")


def seed_redis(r):
    for key in r.keys("zone:*"):
        r.delete(key)
    for z in load_seed():
        r.hset(
            f"zone:{z['location_id']}",
            mapping={
                "borough": z["borough"],
                "zone": z["zone"],
                "service_zone": z["service_zone"],
                "version": str(z["version"]),
            },
        )


def run_client():
    return subprocess.run(
        ["node", str(CLIENT)],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(APP),
    )


def snapshot(r):
    state, versions = {}, {}
    for key in r.keys("zone:*"):
        cid = int(key.split(":", 1)[1])
        h = r.hgetall(key)
        state[cid] = {f: h.get(f) for f in FIELDS}
        versions[cid] = int(h.get("version", "0"))
    return state, versions


@pytest.fixture(scope="module")
def pipeline():
    """Seed a fresh keyspace, run the reconciler twice, capture every artifact."""
    r = connect_redis()
    wait_for_service(effective_http_port())
    seed_redis(r)

    proc1 = run_client()
    assert proc1.returncode == 0, (
        f"first reconcile run failed (rc={proc1.returncode}).\n"
        f"stdout:\n{proc1.stdout}\nstderr:\n{proc1.stderr}"
    )
    assert REPORT_PATH.exists(), (
        f"report not found at {REPORT_PATH}; is reportPath configured correctly?"
    )
    report1_raw = REPORT_PATH.read_text()
    report1 = json.loads(report1_raw)
    state1, versions1 = snapshot(r)

    proc2 = run_client()
    assert proc2.returncode == 0, (
        f"second reconcile run failed (rc={proc2.returncode}).\n"
        f"stdout:\n{proc2.stdout}\nstderr:\n{proc2.stderr}"
    )
    report2 = json.loads(REPORT_PATH.read_text())
    state2, versions2 = snapshot(r)

    exp_report, exp_state, exp_versions = compute_expected()
    return {
        "report1_raw": report1_raw,
        "report1": report1,
        "state1": state1,
        "versions1": versions1,
        "report2": report2,
        "state2": state2,
        "versions2": versions2,
        "exp_report": exp_report,
        "exp_state": exp_state,
        "exp_versions": exp_versions,
    }


# --------------------------------------------------------------------------- #
# Tests                                                                        #
# --------------------------------------------------------------------------- #
def test_report_has_expected_shape(pipeline):
    """The report is valid JSON exposing every documented summary field."""
    report = pipeline["report1"]
    for key in [
        "generated_from",
        "total_zones",
        "reconciled",
        "unchanged",
        "locked_overrides",
        "unknown_zones",
        "changes",
    ]:
        assert key in report, f"report missing key {key!r}"
    assert report["generated_from"] == "redis"
    assert isinstance(report["changes"], list)


def test_report_counts_match_reference(pipeline):
    """Every summary count equals the independently computed reconciliation."""
    report = pipeline["report1"]
    exp = pipeline["exp_report"]
    for key in ["total_zones", "reconciled", "unchanged", "locked_overrides", "unknown_zones"]:
        assert report[key] == exp[key], f"{key}: got {report[key]}, expected {exp[key]}"


def test_report_changes_match_reference(pipeline):
    """The changes list matches by content, ordering (by location_id) and reason."""
    assert pipeline["report1"]["changes"] == pipeline["exp_report"]["changes"]


def test_redis_state_matches_canonical(pipeline):
    """Post-reconcile Redis fields equal the canonical/override target for each zone."""
    state = pipeline["state1"]
    exp_state = pipeline["exp_state"]
    assert set(state) == set(exp_state), "zone id set changed during reconcile"
    for cid, fields in exp_state.items():
        assert state[cid] == fields, f"zone {cid}: got {state[cid]}, expected {fields}"


def test_versions_bumped_only_on_change(pipeline):
    """Version increments by exactly one for changed zones and is untouched otherwise."""
    assert pipeline["versions1"] == pipeline["exp_versions"]


def test_unlocked_override_is_ignored(pipeline):
    """An unlocked operator override must not override the canonical value."""
    canon = load_canonical()
    assert pipeline["state1"][20]["zone"] == canon[20]["zone"]


def test_locked_overrides_applied(pipeline):
    """Locked overrides survive reconciliation and beat the canonical value."""
    overrides = load_overrides()
    state = pipeline["state1"]
    for key, ov in overrides.items():
        if ov.get("locked") is True:
            cid = int(key)
            for f in FIELDS:
                if f in ov:
                    assert state[cid][f] == ov[f], f"locked override for zone {cid}.{f} not applied"


def test_canonical_naming_normalized(pipeline):
    """Drifted casing/whitespace is replaced by exact canonical strings."""
    canon = load_canonical()
    state = pipeline["state1"]
    assert state[12]["zone"] == canon[12]["zone"]
    assert state[12]["zone"] == state[12]["zone"].strip()


def test_unknown_zone_untouched(pipeline):
    """A zone absent from the canonical lookup is left exactly as seeded."""
    seed = {z["location_id"]: z for z in load_seed()}
    canon = load_canonical()
    unknown_ids = [cid for cid in seed if cid not in canon]
    assert unknown_ids, "expected at least one unknown zone in the fixture"
    for cid in unknown_ids:
        original = {f: seed[cid][f] for f in FIELDS}
        assert pipeline["state1"][cid] == original
        assert pipeline["versions1"][cid] == seed[cid]["version"]


def test_reconcile_is_idempotent(pipeline):
    """A second reconcile changes nothing: no report changes, stable Redis state."""
    report2 = pipeline["report2"]
    assert report2["reconciled"] == 0
    assert report2["changes"] == []
    assert pipeline["state2"] == pipeline["state1"]
    assert pipeline["versions2"] == pipeline["versions1"]


def test_report_is_deterministic_bytes(pipeline):
    """Report is emitted with sorted top-level keys and a trailing newline."""
    raw = pipeline["report1_raw"]
    assert raw.endswith("\n"), "report must end with a trailing newline"
    parsed = json.loads(raw)
    top_keys = list(parsed.keys())
    assert top_keys == sorted(top_keys), f"top-level keys not sorted: {top_keys}"


def test_service_reflects_redis_state(pipeline):
    """GET /zones is served from Redis and agrees with a direct keyspace scan."""
    port = effective_http_port()
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/zones", timeout=30) as resp:
        served = json.loads(resp.read().decode("utf-8"))
    served_ids = sorted(z["location_id"] for z in served)
    assert served_ids == sorted(pipeline["state2"].keys())
    by_id = {z["location_id"]: z for z in served}
    for cid, fields in pipeline["state2"].items():
        for f in FIELDS:
            assert by_id[cid][f] == fields[f]
    assert pipeline["report2"]["total_zones"] == len(served_ids)
