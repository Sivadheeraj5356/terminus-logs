"""Verifier for the Meridian Ridge spectral service freeze audit.

Checks three contract areas: the offline Maven build and its dependency
graph, the running service's band-power behaviour under the in-force SMP-7
revision for every enrolled channel, bound-parameter query compliance
observed through PostgreSQL statement logging, and the SOP-9 provenance
dossier. Every request the verifier issues is one documented in
/app/requests/samples.http. Reference values were produced by the oracle
solution inside the task container and are deterministic: the fixed
telemetry holdings and the fixed estimator produce identical spectra on
every run.
"""

import json
import math
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

SERVICE_DIR = Path("/app/service")
JAR_PATH = SERVICE_DIR / "target" / "spectra-svc.jar"
DOSSIER_PATH = Path("/app/audit/provenance_dossier.json")
BASE_URL = "http://127.0.0.1:8747"
PORT = 8747
PG_LOG = Path("/var/log/postgresql/postgresql-16-main.log")

# ---------------------------------------------------------------------------
# BAKED CONSTANTS — produced by the oracle run inside the task container.
# ---------------------------------------------------------------------------

EXPECTED_CHANNELS = ['mag_ridge_e',
 'mag_ridge_n',
 'mag_saddle_w',
 'mag_terrace_c',
 "o'neill_nw",
 'vlf_bench_s']

EXPECTED_BANDS = [('quiet', 0.5, 8.0),
 ('pulse_low', 8.0, 24.0),
 ('pulse_mid', 24.0, 64.0),
 ('pulse_high', 64.0, 128.0),
 ('burst', 128.0, 224.0)]

# (channel, from, to, frames, {band: power}) — one documented reference request
# for every enrolled channel.
EXPECTED_BANDPOWER = [('mag_ridge_e',
  '2025-11-14T00:00:00Z',
  '2025-11-14T00:02:00Z',
  4,
  {'burst': 0.12507405421672485,
   'pulse_high': 0.26672516948267505,
   'pulse_low': 1.2626671014681515e-05,
   'pulse_mid': 0.05347942546789539,
   'quiet': 0.7199401273959533}),
 ('mag_ridge_n',
  '2025-11-14T00:00:16Z',
  '2025-11-14T00:01:04Z',
  3,
  {'burst': 0.045049168824813926,
   'pulse_high': 5.307182248725439e-05,
   'pulse_low': 0.4050803095549315,
   'pulse_mid': 0.1801186876372833,
   'quiet': 5.885411657357896e-06}),
 ('mag_saddle_w',
  '2025-11-14T00:00:00Z',
  '2025-11-14T00:00:32Z',
  2,
  {'burst': 0.00020358276124668668,
   'pulse_high': 0.24521291288742345,
   'pulse_low': 3.3086913387047625e-05,
   'pulse_mid': 0.08003568884657275,
   'quiet': 1.1249545180289686}),
 ('mag_terrace_c',
  '2025-11-14T00:00:32Z',
  '2025-11-14T00:02:00Z',
  2,
  {'burst': 0.3201127738116015,
   'pulse_high': 0.00010122764978588342,
   'pulse_low': 2.5178747033308478e-05,
   'pulse_mid': 0.12509184957729963,
   'quiet': 0.6060205246822148}),
 ("o'neill_nw",
  '2025-11-14T00:00:00Z',
  '2025-11-14T00:00:32Z',
  2,
  {'burst': 0.18008121348801112,
   'pulse_high': 0.1250556109628827,
   'pulse_low': 0.4164653840676218,
   'pulse_mid': 4.825013521200118e-05,
   'quiet': 0.0835166575588494}),
 ('vlf_bench_s',
  '2025-11-14T00:00:16Z',
  '2025-11-14T00:01:04Z',
  3,
  {'burst': 0.0800911133963207,
   'pulse_high': 0.40503653699042724,
   'pulse_low': 0.24488820882882484,
   'pulse_mid': 2.117961566693052e-05,
   'quiet': 4.080882435161181e-06})]

EXPECTED_DOSSIER = {'build_provenance': {'approved_jdbc_version': '42.7.4',
                      'emergency_change_applied_on': '2025-05-20',
                      'emergency_change_reverted_on': '2025-05-28',
                      'emergency_jdbc_version_never_approved': '42.7.3',
                      'jdbc_approval_missing_minute': 'DRB-2024-17',
                      'jdbc_versions_ever_board_approved': 3,
                      'json_library_version': '2.17.2',
                      'math4_migration_status': 'deferred',
                      'math_library_coordinate': 'org.apache.commons:commons-math3:3.6.1',
                      'noncompliant_resolvable_coordinates_count': 1,
                      'pom_revision_entries_recorded': 7,
                      'pom_revisions_reverted_count': 1,
                      'rescinded_jdbc_versions': ['42.2.5', '42.6.0'],
                      'rescinding_advisory': 'MRA-2024-011',
                      'rescinding_advisory_issued': '2024-08-19',
                      'unresolvable_coordinates_count': 2},
 'query_compliance': {'binding_mandate_effective': '2024-01-01',
                      'binding_mandate_memo': 'M-2023-19',
                      'concat_call_sites_in_query_service': 3,
                      'quoted_channel_identifier': "o'neill_nw",
                      'quoted_channel_incident': 'INC-2024-02'},
 'registry_reconciliation': {'advisories_in_force_at_freeze': 2,
                             'advisories_never_registered': 2,
                             'advisories_registered_in_db': 4,
                             'advisories_total_recorded': 6,
                             'audit_freeze_date': '2025-11-30',
                             'foreign_advisories_cited': 2},
 'spectral_method': {'adopted_smp_revision': 'D',
                     'band_count_adopted': 5,
                     'burst_band_bounds_hz': [128.0, 224.0],
                     'interim_fallback_revision': 'B',
                     'rescinded_smp_revision': 'C',
                     'rescinding_erratum': 'E-2024-04',
                     'segment_hop': 512,
                     'segment_length': 1024,
                     'window_normalization': 'sum_w_squared'}}

# ---------------------------------------------------------------------------
# Helpers and fixtures
# ---------------------------------------------------------------------------


def http_get(path, params=None, timeout=30):
    """GET a service endpoint; returns (status, parsed JSON body)."""
    url = BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read().decode())


def port_open(port):
    """True if a TCP connection to the local port succeeds."""
    with socket.socket() as sock:
        sock.settimeout(0.5)
        try:
            sock.connect(("127.0.0.1", port))
            return True
        except OSError:
            return False


def wait_until(predicate, tries=240, interval=0.5):
    """Poll predicate until it returns truthy or the attempts run out."""
    for _ in range(tries):
        if predicate():
            return True
        time.sleep(interval)
    return False


def wait_health(tries=240):
    """Poll /health until the service answers 200."""
    def ready():
        try:
            with urllib.request.urlopen(f"{BASE_URL}/health", timeout=2) as resp:
                return resp.status == 200
        except (urllib.error.URLError, OSError):
            return False
    return wait_until(ready, tries=tries, interval=0.5)


@pytest.fixture(scope="session")
def database():
    """The meridian PostgreSQL cluster, started if not already running."""
    def up():
        probe = subprocess.run(
            ["pg_isready", "-h", "127.0.0.1", "-p", "5432"],
            capture_output=True, timeout=60,
        )
        return probe.returncode == 0

    if not up():
        subprocess.run(["pg_ctlcluster", "16", "main", "start"],
                       capture_output=True, timeout=120)
    assert wait_until(up, tries=120, interval=0.5), "PostgreSQL cluster is not reachable"
    return True


@pytest.fixture(scope="session")
def built_jar(database):
    """Offline Maven build of the service working tree."""
    if JAR_PATH.exists():
        JAR_PATH.unlink()
    proc = subprocess.run(
        ["mvn", "-o", "-B", "-DskipTests", "package"],
        cwd=SERVICE_DIR, capture_output=True, text=True, timeout=420,
    )
    return proc


@pytest.fixture(scope="session")
def service(built_jar):
    """A freshly built service instance listening on 127.0.0.1:8747."""
    assert built_jar.returncode == 0, (
        f"offline build failed:\n{built_jar.stdout[-4000:]}"
    )
    assert JAR_PATH.exists(), "build did not produce target/spectra-svc.jar"
    subprocess.run(["pkill", "-f", "spectra-svc.jar"], capture_output=True)
    assert wait_until(lambda: not port_open(PORT), tries=60, interval=0.25), (
        "a previous service instance did not release port 8747"
    )
    proc = subprocess.Popen(
        ["java", "-jar", str(JAR_PATH)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    assert wait_health(), "service did not become healthy on port 8747"
    yield proc
    proc.terminate()
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()


# ---------------------------------------------------------------------------
# Build and dependency graph
# ---------------------------------------------------------------------------


def test_offline_build_produces_jar(built_jar):
    """`mvn -o -DskipTests package` succeeds against the station repository
    and produces /app/service/target/spectra-svc.jar."""
    assert built_jar.returncode == 0, (
        f"offline build failed:\n{built_jar.stdout[-4000:]}"
    )
    assert JAR_PATH.exists(), "build did not produce target/spectra-svc.jar"


def test_dependency_graph_links_in_force_approvals(built_jar):
    """The resolved dependency graph links exactly the JDBC driver, numerical
    library, and JSON serializer versions whose board approval is in force at
    the freeze date."""
    assert built_jar.returncode == 0, "offline build must succeed first"
    out = Path("/tmp/dep_list.txt")
    if out.exists():
        out.unlink()
    proc = subprocess.run(
        ["mvn", "-o", "-B", "dependency:list", f"-DoutputFile={out}"],
        cwd=SERVICE_DIR, capture_output=True, text=True, timeout=240,
    )
    assert proc.returncode == 0, f"dependency:list failed:\n{proc.stdout[-2000:]}"
    listing = out.read_text()
    for coordinate in (
        "org.postgresql:postgresql:jar:42.7.4",
        "org.apache.commons:commons-math3:jar:3.6.1",
        "com.fasterxml.jackson.core:jackson-databind:jar:2.17.2",
    ):
        assert coordinate in listing, f"approved artifact missing: {coordinate}"


def test_dependency_graph_excludes_noncompliant_versions(built_jar):
    """No rescinded, never-approved, or nonexistent artifact version remains
    in the resolved dependency graph."""
    assert built_jar.returncode == 0, "offline build must succeed first"
    listing = Path("/tmp/dep_list.txt")
    if not listing.exists():
        subprocess.run(
            ["mvn", "-o", "-B", "dependency:list", f"-DoutputFile={listing}"],
            cwd=SERVICE_DIR, capture_output=True, text=True, timeout=240,
        )
    text = listing.read_text()
    for banned in (
        "postgresql:jar:42.2.5",
        "postgresql:jar:42.6.0",
        "postgresql:jar:42.7.3",
        "commons-math4-core",
        "jackson-databind:jar:2.13.4",
        "jackson-databind:jar:2.17.9",
    ):
        assert banned not in text, f"non-compliant artifact linked: {banned}"


# ---------------------------------------------------------------------------
# Service behaviour under the in-force SMP-7 revision, per channel
# ---------------------------------------------------------------------------


def test_health_endpoint(service):
    """/health answers 200 with {"status": "ok"}."""
    status, body = http_get("/health")
    assert status == 200
    assert body == {"status": "ok"}


def test_channels_endpoint_lists_enrolled_stations(service):
    """/channels returns all six enrolled channel identifiers, sorted,
    including the apostrophe-bearing O'Neill Ridge NW identifier verbatim."""
    status, body = http_get("/channels")
    assert status == 200
    assert body.get("channels") == EXPECTED_CHANNELS


def test_bandpower_band_table_is_revision_d(service):
    """Band rows follow the in-force SMP-7 revision: five bands in ascending
    order with the revision D bounds, no guard band, and the response reports
    revision D."""
    channel, frm, to, _frames, _expected = EXPECTED_BANDPOWER[0]
    status, body = http_get(
        "/bandpower", {"channel": channel, "from": frm, "to": to})
    assert status == 200, f"bandpower failed: {body}"
    assert body.get("revision") == "D", "response must report revision D"
    got = [(b["band"], b["lo_hz"], b["hi_hz"]) for b in body["bands"]]
    assert got == EXPECTED_BANDS, f"band table mismatch: {got}"


@pytest.mark.parametrize("case", range(len(EXPECTED_BANDPOWER)))
def test_bandpower_reference_values(service, case):
    """For every enrolled channel, the reported band powers match the
    revision D estimator (symmetric Hann, 1024/512 segmentation, per-segment
    detrending, window-energy scaling, half-open exact-frequency band
    assignment, frame averaging) within 1e-6 relative tolerance."""
    channel, frm, to, frames, expected = EXPECTED_BANDPOWER[case]
    status, body = http_get(
        "/bandpower", {"channel": channel, "from": frm, "to": to})
    assert status == 200, f"bandpower failed for {channel}: {body}"
    assert body["channel"] == channel
    assert body["frames"] == frames, "frame selection must be [from, to)"
    got = {b["band"]: b["power"] for b in body["bands"]}
    assert set(got) == set(expected), f"band names mismatch: {sorted(got)}"
    for band, ref in expected.items():
        assert math.isfinite(got[band]), f"{band} power is not finite"
        assert math.isclose(got[band], ref, rel_tol=1e-6), (
            f"{channel} {band}: got {got[band]:.12g}, expected {ref:.12g}"
        )


def test_quoted_channel_is_served(service):
    """The documented request for the apostrophe-bearing channel succeeds and
    selects its frames — the INC-2024-02 failure mode is fixed."""
    status, body = http_get(
        "/bandpower",
        {"channel": "o'neill_nw",
         "from": "2025-11-14T00:00:00Z", "to": "2025-11-14T00:00:32Z"})
    assert status == 200, f"quoted channel request failed: {body}"
    assert body["frames"] == 2


def test_parameters_reach_postgres_bound(service):
    """The apostrophe-bearing channel value arrives at PostgreSQL as a bound
    parameter of an extended-protocol statement, not interpolated into the
    statement text (observed via the cluster's statement log)."""
    marker = "neill_nw"
    assert PG_LOG.exists(), "cluster statement log not found"
    offset = PG_LOG.stat().st_size
    status, _ = http_get(
        "/bandpower",
        {"channel": "o'neill_nw",
         "from": "2025-11-14T00:00:00Z", "to": "2025-11-14T00:00:32Z"})
    assert status == 200, "documented quoted-channel request should succeed"

    def tail():
        with PG_LOG.open("rb") as fh:
            fh.seek(offset)
            return fh.read().decode(errors="replace")

    assert wait_until(lambda: marker in tail(), tries=60, interval=0.25), (
        "the request value never reached the database log"
    )
    text = tail()
    bound = False
    for line in text.splitlines():
        if marker not in line:
            continue
        if "parameters:" in line:
            bound = True
            continue
        assert "FROM telemetry.readings" not in line, (
            f"request value interpolated into statement text: {line.strip()}"
        )
    assert bound, "no bound-parameter log entry carried the request value"


def test_missing_parameters_rejected(service):
    """The documented request that omits from/to yields a 400 with the
    documented error shape."""
    status, body = http_get("/bandpower", {"channel": "mag_ridge_e"})
    assert status == 400
    assert "error" in body


def test_unknown_channel_not_found(service):
    """The documented request for a channel with no frames in the window
    yields a 404 with the documented error shape."""
    status, body = http_get(
        "/bandpower",
        {"channel": "mag_summit_q",
         "from": "2025-11-14T00:00:00Z", "to": "2025-11-14T00:02:00Z"})
    assert status == 404
    assert "error" in body


# ---------------------------------------------------------------------------
# Provenance dossier
# ---------------------------------------------------------------------------


def test_dossier_exists_with_exact_schema():
    """The dossier exists at /app/audit/provenance_dossier.json and carries
    exactly the four Form PD-4 objects with exactly the schema's keys."""
    assert DOSSIER_PATH.exists(), "provenance dossier not found"
    dossier = json.loads(DOSSIER_PATH.read_text())
    assert set(dossier) == set(EXPECTED_DOSSIER), (
        f"top-level objects mismatch: {sorted(dossier)}"
    )
    for section, expected in EXPECTED_DOSSIER.items():
        assert set(dossier[section]) == set(expected), (
            f"{section} keys mismatch: {sorted(dossier[section])}"
        )


@pytest.mark.parametrize(
    "section",
    ["build_provenance", "query_compliance",
     "spectral_method", "registry_reconciliation"],
)
def test_dossier_section_reconstructs_freeze_record(section):
    """Every field of the dossier section equals the value reconstructed
    from the station archive and registry as of the 2025-11-30 freeze."""
    assert DOSSIER_PATH.exists(), "provenance dossier not found"
    dossier = json.loads(DOSSIER_PATH.read_text())
    assert section in dossier, f"missing section {section}"
    got = dossier[section]
    expected = EXPECTED_DOSSIER[section]
    mismatches = {
        key: (got.get(key), want)
        for key, want in expected.items()
        if got.get(key) != want
    }
    assert not mismatches, f"{section} fields wrong (got, expected): {mismatches}"


def test_maven_available():
    """The Maven toolchain required by the offline build is present."""
    assert shutil.which("mvn"), "mvn not found on PATH"
