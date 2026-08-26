import hashlib
import json
import os
import shutil
import subprocess

JAR = "/app/bin/spoolward.jar"
PLANE = "/app/plane"
DEFAULT_REPORT = "/app/output/spoolward_report.json"
ALT_PLANE = "/tests/fixtures/alt_plane"
SCRATCH = "/tmp/spoolward_scratch"

MAIN_DATA_DIGEST = "9643c09149ec34ae"
MAIN_REPORT_DIGEST = "e85835a71d51efbf"
ALT_DATA_DIGEST = "775333dbbc7707a3"
ALT_REPORT_DIGEST = "fa0b157937d4bbc6"

MAIN_DISPOSITION = {"APPLIED": 18, "DENIED": 4, "NOOP": 3,
                    "UNAUTHORIZED": 2, "VOID": 3}
MAIN_STATE = {"LIVE": 8, "DORMANT": 1, "DETACHED": 1, "PURGED": 4,
              "FLUSHED": 2, "DECOMMISSIONED": 2}
ALT_DISPOSITION = {"APPLIED": 12, "DENIED": 3, "NOOP": 1,
                   "UNAUTHORIZED": 1, "VOID": 1}
ALT_STATE = {"LIVE": 5, "DORMANT": 1, "DETACHED": 0, "PURGED": 3,
             "FLUSHED": 1, "DECOMMISSIONED": 1}


def run_plane(plane=None, report=None, args=None):
    env = dict(os.environ)
    env.pop("SPOOLWARD_PLANE", None)
    env.pop("SPOOLWARD_REPORT", None)
    if plane is not None:
        env["SPOOLWARD_PLANE"] = plane
    if report is not None:
        env["SPOOLWARD_REPORT"] = report
    cmd = ["java", "-jar", JAR] + (args or [])
    return subprocess.run(cmd, capture_output=True, env=env)


def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("utf-8")


def digest_tree(root):
    entries = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            entries.append((rel, full))
    entries.sort(key=lambda e: e[0])
    h = hashlib.sha256()
    for rel, full in entries:
        with open(full, "rb") as f:
            data = f.read()
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(data)
        h.update(b"\x00")
    return h.hexdigest()[:16]


_CACHE = {}


def report_of():
    if "main" not in _CACHE:
        r = run_plane()
        raw = open(DEFAULT_REPORT, "rb").read()
        _CACHE["main"] = (r, raw, json.loads(raw))
    return _CACHE["main"]


def alt_report_of():
    if "alt" not in _CACHE:
        out = os.path.join(SCRATCH, "alt_out", "report.json")
        r = run_plane(plane=ALT_PLANE, report=out)
        raw = open(out, "rb").read()
        _CACHE["alt"] = (r, raw, json.loads(raw))
    return _CACHE["alt"]


def journal_row(rep, cyc, seq):
    rows = [e for e in rep["journal"]
            if e["cycle"] == cyc and e["seq"] == seq]
    assert len(rows) == 1
    return rows[0]


def plane_copy(name):
    dst = os.path.join(SCRATCH, name)
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(PLANE, dst)
    return dst


def drop_lines(root, cyc, needles):
    p = os.path.join(root, "cycles", "cycle_%02d.ndjson" % cyc)
    lines = open(p, "rb").read().decode("utf-8").split("\n")
    kept = [ln for ln in lines
            if not all(n in ln for n in needles) or not ln.strip()]
    with open(p, "wb") as f:
        f.write("\n".join(kept).encode("utf-8"))


# ---------- CLI contract / hygiene surface ----------

def test_run_is_silent_and_zero():
    """A sound run prints nothing and exits zero."""
    r, raw, rep = report_of()
    assert r.returncode == 0
    assert r.stdout == b""
    assert r.stderr == b""


def test_report_has_exactly_nine_members():
    """The report is one object of exactly nine members."""
    r, raw, rep = report_of()
    assert isinstance(rep, dict)
    assert sorted(rep.keys()) == ["by_disposition", "by_index", "by_state",
                                  "cycles_run", "data_digest", "journal",
                                  "orders_seen", "plane_revision",
                                  "report_digest"]


def test_report_is_canonical_with_trailing_newline():
    """Canonical serialization, one trailing line feed."""
    r, raw, rep = report_of()
    assert raw == canon(rep) + b"\n"


def test_plane_counters():
    """plane_revision, cycles_run, orders_seen."""
    r, raw, rep = report_of()
    assert rep["plane_revision"] == 5
    assert rep["cycles_run"] == 4
    assert rep["orders_seen"] == 30


def test_disposition_tally():
    """by_disposition tallies all five answers, all keys stand."""
    r, raw, rep = report_of()
    assert rep["by_disposition"] == MAIN_DISPOSITION


def test_state_tally():
    """by_state tallies all six states with DORMANT apart from LIVE."""
    r, raw, rep = report_of()
    assert rep["by_state"] == MAIN_STATE


def test_orders_seen_equals_sum_and_journal_length():
    """orders_seen sums by_disposition; journal length excludes VOID."""
    r, raw, rep = report_of()
    assert rep["orders_seen"] == sum(rep["by_disposition"].values())
    assert len(rep["journal"]) == rep["orders_seen"] - rep["by_disposition"]["VOID"]
    assert len(rep["journal"]) == 27


def test_every_index_reported():
    """One by_index entry per declared index."""
    r, raw, rep = report_of()
    assert sorted(rep["by_index"].keys()) == [
        "idx-app", "idx-audit", "idx-svc", "idx-sys",
        "idx-tmp", "idx-trace", "idx-web"]


# ---------- by_index rows ----------

def test_serving_index_rows():
    """standing, live and summed volume for serving indices."""
    r, raw, rep = report_of()
    assert rep["by_index"]["idx-sys"] == {"standing": "SERVING",
                                          "live": 2, "volume": 8}
    assert rep["by_index"]["idx-web"] == {"standing": "SERVING",
                                          "live": 1, "volume": 3}


def test_greatest_volume_first_purge_persists():
    """The overflow purged the greatest-volume stream; idx-app keeps 11."""
    r, raw, rep = report_of()
    assert rep["by_index"]["idx-app"] == {"standing": "SERVING",
                                          "live": 2, "volume": 11}


def test_quiesced_index_row_counts_live_streams():
    """A quiesced index still counts its live streams/volume."""
    r, raw, rep = report_of()
    assert rep["by_index"]["idx-tmp"] == {"standing": "QUIESCED",
                                          "live": 1, "volume": 4}


def test_decommissioned_index_row_is_zeroed():
    """A decommissioned index reports live and volume zero."""
    r, raw, rep = report_of()
    assert rep["by_index"]["idx-audit"] == {"standing": "DECOMMISSIONED",
                                            "live": 0, "volume": 0}


def test_pin_survives_quiesce_and_shields_from_purge():
    """worker pinned survived quiesce/resume and was not purged."""
    r, raw, rep = report_of()
    assert rep["by_index"]["idx-svc"] == {"standing": "SERVING",
                                          "live": 2, "volume": 13}
    assert journal_row(rep, 3, 3)["disposition"] == "APPLIED"


def test_cross_phase_route_then_purge():
    """trainer was APPLIED then purged at the retuned index close."""
    r, raw, rep = report_of()
    assert journal_row(rep, 1, 5) == {"cycle": 1, "seq": 5, "kind": "ROUTE",
                                      "subject": "trace-01",
                                      "disposition": "APPLIED"}
    assert rep["by_index"]["idx-trace"] == {"standing": "SERVING",
                                            "live": 1, "volume": 5}


# ---------- journal shape and order ----------

def test_journal_shape_and_order():
    """journal rows, five members, answered order."""
    r, raw, rep = report_of()
    roll = rep["journal"]
    assert len(roll) == 27
    keys = [(e["cycle"], e["seq"]) for e in roll]
    assert keys == sorted(keys)
    for e in roll:
        assert sorted(e.keys()) == ["cycle", "disposition", "kind",
                                    "seq", "subject"]
        assert e["disposition"] != "VOID"
    assert roll[0] == {"cycle": 1, "seq": 1, "kind": "HOLD",
                       "subject": "router", "disposition": "APPLIED"}
    assert roll[-1] == {"cycle": 4, "seq": 5, "kind": "HOLD",
                        "subject": "svc-01", "disposition": "APPLIED"}


def test_screened_lines_never_reach_the_journal():
    """VOID lines are counted but take no journal row."""
    r, raw, rep = report_of()
    assert [e for e in rep["journal"] if e["kind"] == "ARCHIVE"] == []
    assert [e for e in rep["journal"] if e["cycle"] == 1 and e["seq"] == 10] == []


def test_hold_binds_from_either_side():
    """A source-named hold binds the stream; detach is refused."""
    r, raw, rep = report_of()
    assert journal_row(rep, 1, 1) == {"cycle": 1, "seq": 1, "kind": "HOLD",
                                      "subject": "router",
                                      "disposition": "APPLIED"}
    assert journal_row(rep, 2, 1)["disposition"] == "DENIED"
    assert journal_row(rep, 2, 5)["disposition"] == "APPLIED"


def test_flush_forces_through_a_hold():
    """A force flush applies over an outstanding hold."""
    r, raw, rep = report_of()
    assert journal_row(rep, 2, 2) == {"cycle": 2, "seq": 2, "kind": "FLUSH",
                                      "subject": "web-02",
                                      "disposition": "APPLIED"}


def test_barred_pair_never_returns():
    """A flushed source-channel pair is barred from re-route."""
    r, raw, rep = report_of()
    assert journal_row(rep, 3, 2)["disposition"] == "DENIED"


def test_source_uniqueness_is_plane_wide():
    """A bound source is refused a second channel on any index."""
    r, raw, rep = report_of()
    assert journal_row(rep, 2, 4)["disposition"] == "DENIED"


def test_decommission_cascades_and_is_terminal():
    """Decommission cascades; later work on the index is denied."""
    r, raw, rep = report_of()
    assert journal_row(rep, 3, 4)["disposition"] == "APPLIED"
    assert journal_row(rep, 3, 5)["disposition"] == "DENIED"


def test_unauthorized_family():
    """Wrong holding or wrong role answers UNAUTHORIZED."""
    r, raw, rep = report_of()
    assert journal_row(rep, 1, 11)["disposition"] == "UNAUTHORIZED"
    assert journal_row(rep, 4, 3)["disposition"] == "UNAUTHORIZED"


def test_noop_family():
    """Idempotent and empty work answers NOOP."""
    r, raw, rep = report_of()
    assert journal_row(rep, 2, 6)["disposition"] == "NOOP"
    assert journal_row(rep, 2, 7)["disposition"] == "NOOP"
    assert journal_row(rep, 4, 4)["disposition"] == "NOOP"


# ---------- seals ----------

def test_data_digest_matches_the_root():
    """data_digest over the plane root's files."""
    r, raw, rep = report_of()
    assert rep["data_digest"] == MAIN_DATA_DIGEST
    assert digest_tree(PLANE) == MAIN_DATA_DIGEST


def test_report_digest_recomputes():
    """report_digest over the body with the seal absent."""
    r, raw, rep = report_of()
    body = {k: v for k, v in rep.items() if k != "report_digest"}
    again = hashlib.sha256(canon(body)).hexdigest()[:16]
    assert rep["report_digest"] == again
    assert rep["report_digest"] == MAIN_REPORT_DIGEST


# ---------- alt plane ----------

def test_alt_counters_and_digests():
    """The alt plane seals and counters."""
    r, raw, rep = alt_report_of()
    assert r.returncode == 0
    assert r.stdout == b"" and r.stderr == b""
    assert rep["plane_revision"] == 9
    assert rep["cycles_run"] == 3
    assert rep["orders_seen"] == 18
    assert rep["by_disposition"] == ALT_DISPOSITION
    assert rep["by_state"] == ALT_STATE
    assert rep["data_digest"] == ALT_DATA_DIGEST
    assert rep["report_digest"] == ALT_REPORT_DIGEST
    assert digest_tree(ALT_PLANE) == ALT_DATA_DIGEST


def test_alt_index_rows():
    """Alt index standings with a quiesced and decommissioned one."""
    r, raw, rep = alt_report_of()
    assert rep["by_index"]["ix-01"] == {"standing": "QUIESCED",
                                        "live": 1, "volume": 8}
    assert rep["by_index"]["ix-02"] == {"standing": "SERVING",
                                        "live": 2, "volume": 11}
    assert rep["by_index"]["ix-05"] == {"standing": "DECOMMISSIONED",
                                        "live": 0, "volume": 0}


def test_alt_journal_rows():
    """Alt journal dispositions across the families."""
    r, raw, rep = alt_report_of()
    assert len(rep["journal"]) == 17
    assert journal_row(rep, 1, 2)["disposition"] == "DENIED"
    assert journal_row(rep, 1, 8)["disposition"] == "APPLIED"
    assert journal_row(rep, 1, 9)["disposition"] == "APPLIED"
    assert journal_row(rep, 2, 2)["disposition"] == "DENIED"
    assert journal_row(rep, 2, 4)["disposition"] == "DENIED"
    assert journal_row(rep, 3, 3)["disposition"] == "APPLIED"
    assert journal_row(rep, 3, 4)["disposition"] == "UNAUTHORIZED"


# ---------- determinism / immutability / CLI ----------

def test_reruns_are_byte_identical():
    """Two runs over an unchanged root write the same bytes."""
    copy = plane_copy("rerun_plane")
    out1 = os.path.join(SCRATCH, "rerun_a", "r.json")
    out2 = os.path.join(SCRATCH, "rerun_b", "r.json")
    assert run_plane(plane=copy, report=out1).returncode == 0
    assert run_plane(plane=copy, report=out2).returncode == 0
    assert open(out1, "rb").read() == open(out2, "rb").read()


def test_selfcheck_writes_nothing():
    """--selfcheck reads and writes nothing and exits zero."""
    out = os.path.join(SCRATCH, "selfcheck", "r.json")
    r = run_plane(plane=PLANE, report=out, args=["--selfcheck"])
    assert r.returncode == 0
    assert r.stdout == b"" and r.stderr == b""
    assert not os.path.exists(out)


def test_report_directory_is_cleared():
    """The report directory is cleared to the report alone."""
    copy = plane_copy("clear_plane")
    outdir = os.path.join(SCRATCH, "clear_out")
    if os.path.isdir(outdir):
        shutil.rmtree(outdir)
    os.makedirs(os.path.join(outdir, "old_dir"))
    with open(os.path.join(outdir, "stale.json"), "wb") as f:
        f.write(b"{}")
    with open(os.path.join(outdir, "old_dir", "deep.txt"), "wb") as f:
        f.write(b"deep")
    out = os.path.join(outdir, "r.json")
    assert run_plane(plane=copy, report=out).returncode == 0
    assert sorted(os.listdir(outdir)) == ["r.json"]


def test_plane_root_is_untouched():
    """The warden alters nothing under the root."""
    copy = plane_copy("readonly_plane")
    before = digest_tree(copy)
    out = os.path.join(SCRATCH, "readonly_out", "r.json")
    assert run_plane(plane=copy, report=out).returncode == 0
    assert digest_tree(copy) == before


def test_empty_variables_fall_to_defaults():
    """Empty env variables fall to the documented defaults."""
    r, raw, rep = report_of()
    env = dict(os.environ)
    env["SPOOLWARD_PLANE"] = ""
    env["SPOOLWARD_REPORT"] = ""
    r2 = subprocess.run(["java", "-jar", JAR], capture_output=True, env=env)
    assert r2.returncode == 0
    assert open(DEFAULT_REPORT, "rb").read() == raw


# ---------- mutation battery (one per trap family) ----------

def test_mutation_hold_either_side():
    """Drop the source-hold and the detach now applies."""
    copy = plane_copy("mut_hold")
    drop_lines(copy, 1, ['"HOLD"', '"router"'])
    out = os.path.join(SCRATCH, "mut_hold_out", "r.json")
    assert run_plane(plane=copy, report=out).returncode == 0
    rep = json.loads(open(out, "rb").read())
    assert rep["orders_seen"] == 29
    assert journal_row(rep, 2, 1)["disposition"] == "APPLIED"
    assert rep["by_state"]["DETACHED"] == 2
    assert rep["by_state"]["LIVE"] == 7
    assert rep["report_digest"] != MAIN_REPORT_DIGEST


def test_mutation_pair_bar():
    """Drop the flush and the pair is never barred (re-route noops)."""
    copy = plane_copy("mut_bar")
    drop_lines(copy, 1, ['"FLUSH"', '"web-03"'])
    out = os.path.join(SCRATCH, "mut_bar_out", "r.json")
    assert run_plane(plane=copy, report=out).returncode == 0
    rep = json.loads(open(out, "rb").read())
    assert journal_row(rep, 3, 2)["disposition"] == "NOOP"
    assert rep["by_state"]["FLUSHED"] == 1
    assert rep["by_state"]["LIVE"] == 9


def test_mutation_decommission_cascade():
    """Drop the decommission and the index stays reachable/quiescible."""
    copy = plane_copy("mut_decom")
    drop_lines(copy, 3, ['"DECOMMISSION"', '"rx-audit"'])
    out = os.path.join(SCRATCH, "mut_decom_out", "r.json")
    assert run_plane(plane=copy, report=out).returncode == 0
    rep = json.loads(open(out, "rb").read())
    assert rep["by_state"]["DECOMMISSIONED"] == 0
    assert journal_row(rep, 3, 5)["disposition"] == "APPLIED"
    assert rep["by_index"]["idx-audit"] == {"standing": "QUIESCED",
                                            "live": 2, "volume": 11}


def test_mutation_budget_override():
    """Drop the retune and the index no longer overflows."""
    copy = plane_copy("mut_retune")
    drop_lines(copy, 1, ['"RETUNE"', '"idx-trace"'])
    out = os.path.join(SCRATCH, "mut_retune_out", "r.json")
    assert run_plane(plane=copy, report=out).returncode == 0
    rep = json.loads(open(out, "rb").read())
    assert rep["by_state"]["PURGED"] == 3
    assert rep["by_index"]["idx-trace"] == {"standing": "SERVING",
                                            "live": 2, "volume": 15}


def test_mutation_overflow_close():
    """Drop the overflowing route and the close purges nothing there."""
    copy = plane_copy("mut_close")
    drop_lines(copy, 3, ['"ROUTE"', '"sys-03"'])
    out = os.path.join(SCRATCH, "mut_close_out", "r.json")
    assert run_plane(plane=copy, report=out).returncode == 0
    rep = json.loads(open(out, "rb").read())
    assert rep["by_state"]["PURGED"] == 3
    assert rep["by_index"]["idx-sys"] == {"standing": "SERVING",
                                          "live": 2, "volume": 15}


def test_stray_file_moves_only_the_data_digest():
    """An extra file under the root moves only the data seal."""
    r, raw, rep = report_of()
    copy = plane_copy("stray_plane")
    with open(os.path.join(copy, "notes.txt"), "wb") as f:
        f.write(b"ops note\n")
    out = os.path.join(SCRATCH, "stray_out", "r.json")
    assert run_plane(plane=copy, report=out).returncode == 0
    rep2 = json.loads(open(out, "rb").read())
    assert rep2["data_digest"] == digest_tree(copy)
    assert rep2["data_digest"] != MAIN_DATA_DIGEST
    assert rep2["by_disposition"] == rep["by_disposition"]
    assert rep2["by_state"] == rep["by_state"]
    assert rep2["by_index"] == rep["by_index"]
    assert rep2["journal"] == rep["journal"]
