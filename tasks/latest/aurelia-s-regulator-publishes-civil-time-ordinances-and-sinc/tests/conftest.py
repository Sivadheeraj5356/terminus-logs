import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "reference"))

APP = "/app"
CORPUS = "/app/data/ordinances"
OUT = "/app/out"
BIN = "/app/target/release/tzforge"
DSN = "postgresql://tzforge@127.0.0.1:5432/tzforge"
BASE = "http://127.0.0.1:8080"

import civilref  # noqa: E402
import tzread  # noqa: E402


def _run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=900, **kw)


@pytest.fixture(scope="session")
def compiled():
    """Rebuild from the agent's sources, offline, before anything is inspected.

    The image build already produced a binary, so the whole release directory goes
    first. Removing only `target/release/tzforge` is not enough: cargo hardlinks it
    to `target/release/deps/tzforge-<hash>`, so overwriting the binary corrupts the
    cached artefact too, and the next build silently re-links that artefact back
    into place. Everything downstream must run a binary this build compiled from
    the agent's Rust sources, not a leftover or a hand-placed file.
    """
    shutil.rmtree(os.path.join(APP, "target", "release"), ignore_errors=True)
    assert not os.path.exists(BIN), "could not remove the pre-existing %s" % BIN
    env = dict(os.environ, CARGO_NET_OFFLINE="true")
    proc = _run(["cargo", "build", "--release", "--offline"], cwd=APP, env=env)
    assert proc.returncode == 0, "cargo build --release failed:\n%s" % proc.stderr
    assert os.path.exists(BIN), "cargo build reported success but produced no %s" % BIN
    return proc


@pytest.fixture(scope="session")
def postgres(compiled):
    _run(["/app/bin/pgstart.sh"])
    for _ in range(40):
        if _run(["pg_isready", "-h", "127.0.0.1", "-q"]).returncode == 0:
            break
        time.sleep(0.3)
    return True


@pytest.fixture(scope="session")
def built(compiled, postgres):
    """Runs `tzforge build`. Never raises: a failure must surface as a test failure."""
    if not os.path.exists(BIN):
        return subprocess.CompletedProcess([BIN, "build"], 127, "", "binary not built")
    return _run([BIN, "build"])


@pytest.fixture(scope="session")
def rebuilt(built):
    """Snapshots the first build's artefacts, then builds the unchanged corpus again."""
    zoneinfo_dir = os.path.join(OUT, "zoneinfo")
    names = sorted(os.listdir(zoneinfo_dir)) if os.path.isdir(zoneinfo_dir) else []
    before = {n: open(os.path.join(zoneinfo_dir, n), "rb").read() for n in names}
    manifest_before = manifest()
    if not os.path.exists(BIN):
        proc = subprocess.CompletedProcess([BIN, "build"], 127, "", "binary not built")
    else:
        proc = _run([BIN, "build"])
    return {"before": before, "manifest_before": manifest_before, "proc": proc}


@pytest.fixture(scope="session")
def zones():
    """Ground truth recomputed from the committed corpus."""
    return civilref.build_all(CORPUS)


@pytest.fixture(scope="session")
def db(built):
    import psycopg2
    con = psycopg2.connect(DSN)
    con.autocommit = True
    yield con
    con.close()


@pytest.fixture(scope="session")
def server(built):
    proc = subprocess.Popen([BIN, "serve"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    ready = False
    for _ in range(60):
        if proc.poll() is not None:
            break
        try:
            urllib.request.urlopen(BASE + "/v1/zones", timeout=1).read()
            ready = True
            break
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.25)
    yield (proc, ready)
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


# ----------------------------------------------------------------- helpers
def zone_path(name):
    return os.path.join(OUT, "zoneinfo", name)


def zone_bytes(name):
    try:
        with open(zone_path(name), "rb") as fh:
            return fh.read()
    except OSError:
        return b""


def manifest():
    try:
        with open(os.path.join(OUT, "manifest.json"), "rb") as fh:
            return fh.read()
    except OSError:
        return b""


def parsed(name):
    raw = zone_bytes(name)
    if not raw:
        pytest.fail("no zone file for %s" % name)
    return tzread.parse(raw)


def get_json(path, headers=None):
    req = urllib.request.Request(BASE + path, headers=headers or {})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, json.loads(r.read().decode())


def post_json(path, body):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, json.loads(r.read().decode())


def http_status(path, headers=None, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    hdrs = dict(headers or {})
    if data is not None:
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read(), {k.lower(): v for k, v in r.headers.items()}
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), {k.lower(): v for k, v in exc.headers.items()}


def zdump(path, lo, hi):
    proc = _run(["zdump", "-v", "-c", "%d,%d" % (lo, hi), path])
    rows = []
    for line in proc.stdout.splitlines():
        if "isdst=" not in line or "NULL" in line:
            continue
        parts = line.split()
        rows.append({
            "isdst": int(parts[-2].split("=")[1]),
            "gmtoff": int(parts[-1].split("=")[1]),
            "abbrev": parts[-3],
        })
    return rows, proc.returncode


def glibc_at(path, epoch):
    env = {"TZ": ":" + path, "PATH": "/usr/bin:/bin"}
    proc = subprocess.run(["date", "-d", "@%d" % epoch, "+%::z %Z"],
                          capture_output=True, text=True, env=env, timeout=30)
    off, abbrev = proc.stdout.split()
    sign = 1 if off[0] == "+" else -1
    h, m, sec = (int(x) for x in off[1:].split(":"))
    return sign * (h * 3600 + m * 60 + sec), abbrev
