import datetime
import hashlib
import json
import os
import zoneinfo

import psycopg2
import pytest

import civilref
import tzread
from civilref.civil import civil_from_days, days_from_civil
from civilref.timeline import HORIZON, INT32_MAX, INT32_MIN
from conftest import (CORPUS, get_json, glibc_at, http_status, manifest, parsed,
                      post_json, zone_bytes, zone_path)

MIGRATIONS = "/app/migrations"
DIGESTS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "reference", "expected_digests.json")


def tree_digest(root):
    h = hashlib.sha256()
    for base, dirs, files in os.walk(root):
        dirs.sort()
        for name in sorted(files):
            path = os.path.join(base, name)
            h.update(os.path.relpath(path, root).encode())
            with open(path, "rb") as fh:
                h.update(fh.read())
    return h.hexdigest()


def fmt_local(secs):
    y, m, d = civil_from_days(secs // 86400)
    rem = secs % 86400
    return "%04d-%02d-%02dT%02d:%02d:%02d" % (y, m, d, rem // 3600,
                                              (rem % 3600) // 60, rem % 60)


def zdump_epochs(path, lo, hi):
    """zdump rows keyed by the UT instant they describe."""
    import subprocess
    proc = subprocess.run(["zdump", "-v", "-c", "%d,%d" % (lo, hi), path],
                          capture_output=True, text=True, timeout=300)
    months = {m: i + 1 for i, m in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}
    rows = {}
    for line in proc.stdout.splitlines():
        if "isdst=" not in line or "NULL" in line or " UT = " not in line:
            continue
        head = line.split(" UT = ")[0]
        parts = head.split()
        try:
            mon = months[parts[-4]]
            day = int(parts[-3])
            hh, mm, ss = (int(x) for x in parts[-2].split(":"))
            year = int(parts[-1])
        except (KeyError, ValueError, IndexError):
            continue
        epoch = days_from_civil(year, mon, day) * 86400 + hh * 3600 + mm * 60 + ss
        tail = line.split()
        rows[epoch] = (int(tail[-1].split("=")[1]), int(tail[-2].split("=")[1]),
                       tail[-3])
    return rows, proc.returncode


# ----------------------------------------------------------- derivation, idempotency
def test_build_exits_zero_and_creates_all_outputs(built, zones):
    assert built.returncode == 0, built.stderr
    for name in zones:
        assert os.path.exists(zone_path(name)), name
    assert manifest()


def test_manifest_is_canonical_sorted_json(built, zones):
    raw = manifest()
    assert raw.endswith(b"\n")
    doc = json.loads(raw)
    names = [e["zone"] for e in doc["zones"]]
    assert names == sorted(names) == sorted(zones)
    canonical = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    assert raw == canonical


def test_manifest_hash_matches_file_bytes(built, zones):
    doc = json.loads(manifest())
    for entry in doc["zones"]:
        tl = zones[entry["zone"]]
        raw = zone_bytes(entry["zone"])
        assert entry["sha256"] == hashlib.sha256(raw).hexdigest()
        assert entry["transition_count"] == len(tl.transitions)
        assert entry["first_transition"] == tl.transitions[0].ut
        assert entry["last_transition"] == tl.transitions[-1].ut


def test_rebuild_is_byte_identical(rebuilt, zones):
    assert rebuilt["proc"].returncode == 0, rebuilt["proc"].stderr
    assert sorted(rebuilt["before"]) == sorted(zones)
    for name in zones:
        assert rebuilt["before"][name] == zone_bytes(name), name
    assert rebuilt["manifest_before"] == manifest()


def test_rebuild_does_not_duplicate_or_orphan_db_rows(db, rebuilt, zones):
    cur = db.cursor()
    for table, expected in (
        ("zones", len(zones)),
        ("transitions", sum(len(z.transitions) for z in zones.values())),
        ("segments", sum(len(z.segments) for z in zones.values())),
        ("ordinances", sum(len(z.ordinances) for z in zones.values())),
    ):
        cur.execute("SELECT count(*) FROM %s" % table)
        assert cur.fetchone()[0] == expected, table


def test_corpus_and_migrations_unmodified():
    with open(DIGESTS) as fh:
        expected = json.load(fh)
    assert tree_digest(CORPUS) == expected["corpus"]
    assert tree_digest(MIGRATIONS) == expected["migrations"]


# ----------------------------------------------------------------- zone file fidelity
def test_tzif_magic_version_and_header_counts(built, zones):
    for name in zones:
        raw = zone_bytes(name)
        assert raw[:4] == b"TZif", name
        assert raw[4:5] == b"2", name
        assert raw[5:20] == b"\x00" * 15, name
        head = tzread.counts_of(raw)
        assert head["leapcnt"] == 0
        assert head["isutcnt"] == head["isstdcnt"] == head["typecnt"]
        t = tzread.parse(raw)
        assert len(t.v2.types) == head["typecnt"]


def test_tzif_v1_block_present_and_clipped_to_int32(built, zones):
    for name, tl in zones.items():
        t = parsed(name)
        expected = [tr.ut for tr in tl.transitions if INT32_MIN <= tr.ut <= INT32_MAX]
        assert t.v1.transitions == expected, name
        assert all(INT32_MIN <= x <= INT32_MAX for x in t.v1.transitions)
        assert len(t.v1.types) == len(t.v2.types), name


def test_tzif_1901_transition_present_in_64bit_block_only(built, zones):
    clipped = 0
    for name, tl in zones.items():
        t = parsed(name)
        below = [tr.ut for tr in tl.transitions if tr.ut < INT32_MIN]
        if not below:
            continue
        clipped += 1
        assert [x for x in t.v2.transitions if x < INT32_MIN] == below, name
        assert not [x for x in t.v1.transitions if x < INT32_MIN], name
        assert len(t.v2.transitions) == len(t.v1.transitions) + len(below), name
    assert clipped, "no jurisdiction exercises the 32-bit clipping rule"


def test_tzif_types_ordered_by_first_use(built, zones):
    for name, tl in zones.items():
        t = parsed(name)
        assert t.v2.types[0][0] == tl.meridian, name
        assert t.v2.abbrev(t.v2.types[0][2]) == "LMT", name
        assert t.v2.types[0][1] == 0
        seen = [0]
        for idx in t.v2.indices:
            if idx not in seen:
                assert idx == len(seen), "%s: type %d used out of order" % (name, idx)
                seen.append(idx)
        assert len(seen) == len(t.v2.types), name


def test_tzif_abbrev_buffer_packing_no_suffix_sharing(built, zones):
    for name in zones:
        t = parsed(name)
        entries = t.v2.chars.split(b"\x00")
        assert entries[-1] == b"", name
        entries = entries[:-1]
        assert len(entries) == len(t.v2.types), name
        offset = 0
        for i, ent in enumerate(entries):
            assert t.v2.types[i][2] == offset, name
            offset += len(ent) + 1


def test_tzif_isstd_isut_indicators_follow_anchor_kind(built, zones):
    for name, tl in zones.items():
        t = parsed(name)
        assert t.v2.isstd == [ty[3] for ty in tl.types], name
        assert t.v2.isut == [ty[4] for ty in tl.types], name
        for std, ut in zip(t.v2.isstd, t.v2.isut):
            assert not (ut == 1 and std == 0), name


def test_tzif_no_redundant_consecutive_transitions(built, zones):
    for name, tl in zones.items():
        t = parsed(name)
        states = tzread.states(t.v2)
        lmt = (tl.meridian, 0, "LMT")
        assert states[0] != lmt, name
        for a, b in zip(states, states[1:]):
            assert a != b, name
        assert t.v2.transitions == sorted(set(t.v2.transitions)), name


def test_tzif_bytes_match_reference_all_zones(built, zones):
    for name, tl in zones.items():
        assert zone_bytes(name) == civilref.serialize(tl), name


# --------------------------------------------------------------------- foreign readers
def test_zdump_transition_dump_matches_reference(built, zones):
    for name, tl in zones.items():
        rows, rc = zdump_epochs(zone_path(name), 1901, 2039)
        assert rc == 0, name
        assert rows, name
        checked = 0
        for tr in tl.transitions:
            if tr.ut not in rows:
                continue
            gmtoff, isdst, abbrev = rows[tr.ut]
            assert (gmtoff, isdst, abbrev) == (tr.utoff, tr.isdst, tr.abbrev), \
                "%s at %d" % (name, tr.ut)
            checked += 1
        assert checked > len(tl.transitions) // 2, name


def test_zdump_beyond_horizon_matches_footer_expansion(built, zones):
    seasonal = 0
    for name, tl in zones.items():
        rows, rc = zdump_epochs(zone_path(name), 2039, 2043)
        assert rc == 0, name
        if "," not in tl.footer:
            # An offset-only footer recurs never; only the fixed offset can be read.
            assert not rows, "%s: a fixed-offset footer cannot transition" % name
            secs, abbrev = glibc_at(zone_path(name), 2270000000)
            assert (secs, abbrev) == civilref.local_at(tl, 2270000000)[0::2], name
            continue
        seasonal += 1
        assert rows, "%s: zdump reports nothing past the horizon" % name
        for epoch, (gmtoff, isdst, abbrev) in rows.items():
            assert epoch > HORIZON
            expected = civilref.local_at(tl, epoch)
            assert (gmtoff, isdst, abbrev) == expected, "%s at %d" % (name, epoch)
    assert seasonal >= 10


def test_glibc_date_offsets_match_reference_sample(built, zones):
    for name, tl in zones.items():
        probes = [tr.ut for tr in tl.transitions[::20]]
        probes += [tr.ut - 1 for tr in tl.transitions[::20]]
        probes += [2240000000, 2300000000, 2360000000]
        for epoch in probes:
            secs, abbrev = glibc_at(zone_path(name), epoch)
            utoff, _, want = civilref.local_at(tl, epoch)
            assert secs == utoff, "%s at %d" % (name, epoch)
            assert abbrev == want, "%s at %d" % (name, epoch)


def test_python_zoneinfo_agrees_with_zdump(built, zones):
    for name, tl in zones.items():
        with open(zone_path(name), "rb") as fh:
            tz = zoneinfo.ZoneInfo.from_file(fh, key=name)
        rows, _ = zdump_epochs(zone_path(name), 1901, 2043)
        assert rows, name
        for epoch, (gmtoff, isdst, abbrev) in list(rows.items())[::5]:
            moment = datetime.datetime.fromtimestamp(epoch, tz)
            assert int(moment.utcoffset().total_seconds()) == gmtoff, "%s %d" % (name, epoch)
            assert moment.tzname() == abbrev, "%s %d" % (name, epoch)
            assert int(bool(moment.dst())) == isdst, "%s %d" % (name, epoch)


# ------------------------------------------------------------ precedence and ordinances
def test_precedence_uses_enactment_not_effective_date(db, server, zones):
    tl = zones["Ossary-Bight"]
    probe = days_from_civil(1991, 6, 1) * 86400
    expected = next(s.ordinance for s in reversed(tl.segments) if s.start <= probe)
    assert expected == "ORD-1993-01"
    _, body = get_json("/v1/at?zone=Ossary-Bight&epoch=%d" % probe)
    assert body["ordinance"] == expected
    cur = db.cursor()
    cur.execute("SELECT ordinance FROM segments WHERE zone=%s AND valid @> to_timestamp(%s)",
                ("Ossary-Bight", probe))
    assert cur.fetchone()[0] == expected


def test_retroactive_amendment_governs_its_window(db, zones):
    tl = zones["Ossary-Bight"]
    seg = next(s for s in tl.segments if s.ordinance == "ORD-1993-01")
    cur = db.cursor()
    cur.execute("SELECT lower(valid) FROM segments WHERE zone=%s AND ordinance=%s",
                ("Ossary-Bight", "ORD-1993-01"))
    lower = cur.fetchone()[0]
    assert int(lower.timestamp()) == seg.start
    cur.execute("SELECT effective_epoch, enacted FROM ordinances WHERE zone=%s AND ordinance=%s",
                ("Ossary-Bight", "ORD-1993-01"))
    eff, enacted = cur.fetchone()
    assert eff < days_from_civil(enacted.year, enacted.month, enacted.day) * 86400


def test_repeal_preserves_prior_transitions(db, zones):
    tl = zones["Sable-Point"]
    want = [t.ut for t in tl.transitions if t.ordinance == "ORD-1971-02"]
    assert want
    cur = db.cursor()
    cur.execute("SELECT at_epoch FROM transitions WHERE zone=%s AND ordinance=%s ORDER BY at_epoch",
                ("Sable-Point", "ORD-1971-02"))
    assert [r[0] for r in cur.fetchall()] == want
    cur.execute("SELECT effective_epoch FROM ordinances WHERE zone=%s AND ordinance=%s",
                ("Sable-Point", "ORD-1985-01"))
    repeal_at = cur.fetchone()[0]
    assert max(want) < repeal_at


def test_repeal_returns_governance_to_the_next_ordinance(db, zones):
    tl = zones["Sable-Point"]
    cur = db.cursor()
    cur.execute("SELECT effective_epoch FROM ordinances WHERE zone=%s AND ordinance=%s",
                ("Sable-Point", "ORD-1985-01"))
    repeal_at = cur.fetchone()[0]
    after = next(s.ordinance for s in reversed(tl.segments) if s.start <= repeal_at)
    assert after != "ORD-1971-02"
    cur.execute("SELECT ordinance FROM segments WHERE zone=%s AND valid @> to_timestamp(%s)",
                ("Sable-Point", repeal_at))
    assert cur.fetchone()[0] == after


def test_never_effective_ordinance_emits_nothing(db, zones):
    tl = zones["Kestrel-Marrow"]
    assert not [t for t in tl.transitions if t.ordinance == "ORD-1987-02"]
    cur = db.cursor()
    cur.execute("SELECT count(*) FROM transitions WHERE zone=%s AND ordinance=%s",
                ("Kestrel-Marrow", "ORD-1987-02"))
    assert cur.fetchone()[0] == 0
    cur.execute("SELECT count(*) FROM segments WHERE zone=%s AND ordinance=%s",
                ("Kestrel-Marrow", "ORD-1987-02"))
    assert cur.fetchone()[0] == 0
    cur.execute("SELECT kind FROM ordinances WHERE zone=%s AND ordinance=%s",
                ("Kestrel-Marrow", "ORD-1987-02"))
    assert cur.fetchone()[0] == "establish"


def test_two_hour_jump_preserved(db, zones):
    tl = zones["Aurelia-Vantor"]
    before = [tl.meridian] + [t.utoff for t in tl.transitions[:-1]]
    jumps = [t.ut for t, prev in zip(tl.transitions, before) if t.utoff - prev == 7200]
    assert jumps, "the two-hour jump is not in the reference timeline"
    cur = db.cursor()
    cur.execute("SELECT at_epoch FROM transitions WHERE zone=%s "
                "AND utoff_after - utoff_before = 7200 ORDER BY at_epoch",
                ("Aurelia-Vantor",))
    assert [r[0] for r in cur.fetchall()] == jumps


def test_basis_chain_resolves_standard_offset(db, zones):
    cur = db.cursor()
    for name, tl in zones.items():
        want = {o.oid: std for o, std, _, _ in tl.ordinances if std is not None}
        cur.execute("SELECT ordinance, standard_offset FROM ordinances "
                    "WHERE zone=%s AND kind='establish'", (name,))
        assert dict(cur.fetchall()) == want, name


def test_seceded_jurisdiction_lineage_inherited(db, zones):
    shoal = {o.oid for o, _, _, _ in zones["Talveny-Shoal"].ordinances}
    reach = {o.oid for o, _, _, _ in zones["Talveny-Reach"].ordinances}
    assert shoal & reach, "no inherited ordinances"
    cur = db.cursor()
    cur.execute("SELECT ordinance FROM ordinances WHERE zone=%s", ("Talveny-Shoal",))
    assert {r[0] for r in cur.fetchall()} == shoal


def test_lmt_initial_type_from_meridian(built, zones):
    for name, tl in zones.items():
        t = parsed(name)
        assert t.v2.types[0] == (tl.meridian, 0, t.v2.types[0][2]), name
        assert t.v2.abbrev(t.v2.types[0][2]) == "LMT"
        assert tl.meridian != tl.transitions[0].utoff, name


# ------------------------------------------------------------------ calendar, anchoring
def _effective(db, zone, oid):
    cur = db.cursor()
    cur.execute("SELECT effective_epoch FROM ordinances WHERE zone=%s AND ordinance=%s",
                (zone, oid))
    return cur.fetchone()[0]


def test_wall_anchor_uses_offset_in_force_before(db, zones):
    tl = zones["Aurelia-Vantor"]
    o, std, _, eff = next(x for x in tl.ordinances if x[0].oid == "ORD-1945-02")
    assert o.eff_anchor == "wall"
    assert _effective(db, "Aurelia-Vantor", "ORD-1945-02") == eff
    naive = o.eff_civil - std
    assert eff != naive, "the wall anchor is inert for this ordinance"


def test_standard_anchor_ignores_save(db, zones):
    tl = zones["Sable-Verge"]
    o, std, _, eff = next(x for x in tl.ordinances if x[0].oid == "ORD-1957-01")
    assert o.eff_anchor == "standard"
    assert _effective(db, "Sable-Verge", "ORD-1957-01") == eff
    assert eff != o.eff_civil - std
    prev_utoff = civilref.local_at(tl, eff - 1)[0]
    assert eff != o.eff_civil - prev_utoff, "the standard anchor is inert here"


def test_universal_anchor_taken_as_is(db, zones):
    found = 0
    for name, tl in zones.items():
        for o, _, _, eff in tl.ordinances:
            if o.eff_anchor != "universal":
                continue
            assert eff == o.eff_civil, "%s %s" % (name, o.oid)
            assert _effective(db, name, o.oid) == eff
            found += 1
    assert found


def test_southern_hemisphere_state_at_year_boundary(server, zones):
    tl = zones["Talveny-Reach"]
    seg = next(s for s in tl.segments if s.ordinance == "ORD-1971-01")
    utoff, isdst, _ = civilref.local_at(tl, seg.start)
    assert isdst == 1, "carry-over from the previous October is not exercised"
    _, body = get_json("/v1/at?zone=Talveny-Reach&epoch=%d" % seg.start)
    assert (body["utoff"], body["isdst"]) == (utoff, isdst)


def test_time_of_day_rollover_past_24h(built, zones):
    tl = zones["Aurelia-Corrin"]
    t = parsed("Aurelia-Corrin")
    assert t.v2.transitions == [tr.ut for tr in tl.transitions]
    assert "/24" in tl.footer, "the 24:00 rule does not reach the footer"
    assert t.footer == tl.footer


def test_day_specifier_variants(built, zones):
    tl = zones["Merrow-Kell"]
    t = parsed("Merrow-Kell")
    assert t.v2.transitions == [tr.ut for tr in tl.transitions]
    assert tzread.states(t.v2) == [(x.utoff, x.isdst, x.abbrev) for x in tl.transitions]


def test_pre1970_weekday_resolution(built, zones):
    checked = 0
    for name, tl in zones.items():
        t = parsed(name)
        early_ref = [tr.ut for tr in tl.transitions if tr.ut < 0]
        early_got = [x for x in t.v2.transitions if x < 0]
        assert early_got == early_ref, name
        checked += len(early_ref)
    assert checked > 200, "too few pre-1970 transitions to exercise weekday maths"


def test_negative_save_sets_isdst_and_labels(built, zones):
    tl = zones["Kestrel-Downs"]
    winter = [t for t in tl.transitions if t.isdst == 1 and t.abbrev == "GMT"]
    assert winter, "negative save is not exercised"
    t = parsed("Kestrel-Downs")
    states = tzread.states(t.v2)
    assert (winter[0].utoff, 1, "GMT") in states
    assert winter[0].utoff < tl.perpetual_stdoff if hasattr(tl, "perpetual_stdoff") else True
    assert states == [(x.utoff, x.isdst, x.abbrev) for x in tl.transitions]


def test_numeric_label_formatting(built, zones):
    seen = set()
    for name, tl in zones.items():
        t = parsed(name)
        assert tzread.states(t.v2) == [(x.utoff, x.isdst, x.abbrev) for x in tl.transitions], name
        seen |= {x.abbrev for x in tl.transitions if x.abbrev[0] in "+-"}
    assert any(len(a) == 3 for a in seen), "no +HH label"
    assert any(len(a) == 5 for a in seen), "no +HHMM label"


# ------------------------------------------------------------------------ POSIX footer
def test_footer_offset_sign_inversion(built, zones):
    tl = zones["Aurelia-Vantor"]
    t = parsed("Aurelia-Vantor")
    assert t.footer == tl.footer
    assert t.footer.startswith("WAT-7"), t.footer


def test_footer_brackets_numeric_abbrevs(built, zones):
    t = parsed("Aurelia-Corrin")
    assert t.footer.startswith("<"), t.footer
    assert t.footer == zones["Aurelia-Corrin"].footer


def test_footer_week_number_mapping(built, zones):
    for name in ("Merrow-Strand", "Sable-Verge"):
        t = parsed(name)
        assert t.footer == zones[name].footer
        assert ".2.0" in t.footer, "%s: Sun>=8 must map to the second Sunday" % name
    t = parsed("Aurelia-Vantor")
    assert ".5.0" in t.footer, "lastSun must map to week 5"


def test_footer_swaps_slots_for_negative_save(built, zones):
    tl = zones["Kestrel-Downs"]
    t = parsed("Kestrel-Downs")
    assert t.footer == tl.footer
    std, dst = t.footer.split(",")[0][:3], "GMT"
    assert std == "IST" and dst in t.footer
    winter = days_from_civil(2041, 1, 15) * 86400
    secs, abbrev = glibc_at(zone_path("Kestrel-Downs"), winter)
    assert (secs, abbrev) == civilref.local_at(tl, winter)[0::2]


def test_footer_offset_only_when_no_perpetual_rule(built, zones):
    t = parsed("Ossary-Fen")
    assert "," not in t.footer, t.footer
    assert t.footer == zones["Ossary-Fen"].footer


# --------------------------------------------------------------------------- the index
def test_segments_overlapping_insert_is_rejected(db, zones):
    cur = db.cursor()
    cur.execute("SELECT zone, lower(valid), ordinance, standard_offset FROM segments "
                "WHERE upper(valid) IS NOT NULL LIMIT 1")
    zone, lower, ordinance, stdoff = cur.fetchone()
    con = psycopg2.connect("postgresql://tzforge@127.0.0.1:5432/tzforge")
    try:
        with con, con.cursor() as c2:
            with pytest.raises(psycopg2.errors.ExclusionViolation):
                c2.execute(
                    "INSERT INTO segments (zone, valid, ordinance, standard_offset) "
                    "VALUES (%s, tstzrange(%s, %s + interval '1 day', '[)'), %s, %s)",
                    (zone, lower, lower, ordinance, stdoff))
    finally:
        con.close()


def test_segments_match_governing_intervals(db, zones):
    cur = db.cursor()
    for name, tl in zones.items():
        cur.execute("SELECT lower(valid), upper(valid), ordinance, standard_offset "
                    "FROM segments WHERE zone=%s ORDER BY lower(valid)", (name,))
        rows = [(int(a.timestamp()), int(b.timestamp()) if b else None, o, s)
                for a, b, o, s in cur.fetchall()]
        want = [(s.start, s.end, s.ordinance, s.stdoff) for s in tl.segments]
        assert rows == want, name


def test_transitions_table_matches_reference(db, zones):
    cur = db.cursor()
    for name, tl in zones.items():
        cur.execute("SELECT at_epoch, utoff_before, utoff_after, isdst_after, "
                    "abbrev_after, ordinance FROM transitions WHERE zone=%s "
                    "ORDER BY at_epoch", (name,))
        rows = cur.fetchall()
        before = [tl.meridian] + [t.utoff for t in tl.transitions[:-1]]
        want = [(t.ut, p, t.utoff, t.isdst, t.abbrev, t.ordinance)
                for t, p in zip(tl.transitions, before)]
        assert rows == want, name


def test_ordinances_basis_chains_resolve_via_recursive_cte(db, zones):
    cur = db.cursor()
    cur.execute("""
        WITH RECURSIVE chain(zone, ordinance, head, depth) AS (
            SELECT zone, ordinance, ordinance, 0 FROM ordinances
             WHERE kind = 'establish' AND basis IS NOT NULL
            UNION ALL
            SELECT c.zone, c.ordinance, o.basis, c.depth + 1
              FROM chain c
              JOIN ordinances o ON o.zone = c.zone AND o.ordinance = c.head
             WHERE o.basis IS NOT NULL AND c.depth < 32
        )
        SELECT c.zone, c.ordinance, c.head, c.depth FROM chain c
          JOIN ordinances t ON t.zone = c.zone AND t.ordinance = c.head
         WHERE t.basis IS NULL
    """)
    resolved = cur.fetchall()
    assert resolved, "no basis chains in the index"
    assert max(r[3] for r in resolved) >= 2, "no chain deeper than two links"
    for zone, ordinance, head, _ in resolved:
        cur.execute("SELECT standard_offset FROM ordinances WHERE zone=%s AND ordinance=%s",
                    (zone, ordinance))
        got = cur.fetchone()[0]
        cur.execute("SELECT standard_offset FROM ordinances WHERE zone=%s AND ordinance=%s",
                    (zone, head))
        assert got == cur.fetchone()[0], "%s %s" % (zone, ordinance)


def test_zones_table_matches_manifest_and_footer(db, zones):
    doc = {e["zone"]: e for e in json.loads(manifest())["zones"]}
    cur = db.cursor()
    cur.execute("SELECT zone, meridian_seconds, tzif_sha256, transition_count, "
                "first_transition, last_transition, posix_footer FROM zones")
    rows = {r[0]: r[1:] for r in cur.fetchall()}
    assert set(rows) == set(zones)
    for name, tl in zones.items():
        meridian, sha, count, first, last, footer = rows[name]
        assert meridian == tl.meridian
        assert sha == doc[name]["sha256"]
        assert count == len(tl.transitions)
        assert (first, last) == (tl.transitions[0].ut, tl.transitions[-1].ut)
        assert footer == tl.footer


# ------------------------------------------------------------------------- the service
def test_at_endpoint_matches_reference_around_every_transition(server, zones):
    proc, ready = server
    assert ready, "the service did not come up"
    for name, tl in zones.items():
        for tr in tl.transitions:
            for probe in (tr.ut - 1, tr.ut):
                _, body = get_json("/v1/at?zone=%s&epoch=%d" % (name, probe))
                utoff, isdst, abbrev = civilref.local_at(tl, probe)
                assert (body["utoff"], body["isdst"], body["abbrev"]) == \
                    (utoff, isdst, abbrev), "%s at %d" % (name, probe)


def test_at_endpoint_beyond_the_horizon_uses_the_footer_rule(server, zones):
    for name, tl in zones.items():
        for probe in (2240000000, 2300000000, 2360000000):
            _, body = get_json("/v1/at?zone=%s&epoch=%d" % (name, probe))
            utoff, isdst, abbrev = civilref.local_at(tl, probe)
            assert (body["utoff"], body["isdst"], body["abbrev"]) == (utoff, isdst, abbrev)


def test_resolve_gap_and_fold_policies(server, zones):
    """Classification comes from the reference: adjacent offsets alone do not decide it
    when two transitions fall within hours of each other."""
    gaps = folds = 0
    for name, tl in zones.items():
        before = [tl.meridian] + [t.utoff for t in tl.transitions[:-1]]
        for tr, prev in list(zip(tl.transitions, before))[::7]:
            for local in (tr.ut + prev + 1, tr.ut + tr.utoff + 1):
                _, kind = civilref.resolve_local(tl, local, "reject", 0)
                stamp = fmt_local(local)
                if kind == "gap":
                    status, _, _ = http_status(
                        "/v1/resolve", method="POST",
                        body={"zone": name, "local": stamp, "policy": "reject"})
                    assert status == 409, "%s %s" % (name, stamp)
                    _, body = post_json("/v1/resolve", {
                        "zone": name, "local": stamp, "policy": "shift"})
                    want, _ = civilref.resolve_local(tl, local, "shift", 0)
                    assert body["kind"] == "gap"
                    assert body["epoch"] == want, "%s %s" % (name, stamp)
                    gaps += 1
                elif kind == "fold":
                    _, early = post_json("/v1/resolve", {
                        "zone": name, "local": stamp, "fold": 0})
                    _, late = post_json("/v1/resolve", {
                        "zone": name, "local": stamp, "fold": 1})
                    assert early["kind"] == late["kind"] == "fold"
                    assert early["epoch"] == civilref.resolve_local(tl, local, "reject", 0)[0]
                    assert late["epoch"] == civilref.resolve_local(tl, local, "reject", 1)[0]
                    assert late["epoch"] > early["epoch"]
                    folds += 1
                else:
                    _, body = post_json("/v1/resolve", {"zone": name, "local": stamp})
                    assert body["kind"] == "unique"
                    assert body["epoch"] == civilref.resolve_local(tl, local, "reject", 0)[0]
    assert gaps > 15 and folds > 15, (gaps, folds)


def test_resolve_unique_civil_time(server, zones):
    tl = zones["Ossary-Fen"]
    local = days_from_civil(2000, 6, 15) * 86400 + 12 * 3600
    _, body = post_json("/v1/resolve", {"zone": "Ossary-Fen", "local": fmt_local(local)})
    assert body["kind"] == "unique"
    assert civilref.local_at(tl, body["epoch"])[0] == local - body["epoch"]


def test_transitions_pagination_is_stable_and_ascending(server, zones):
    for name, tl in zones.items():
        collected = []
        cursor = None
        for _ in range(200):
            path = "/v1/transitions?zone=%s&limit=50" % name
            if cursor is not None:
                path += "&cursor=%d" % cursor
            _, body = get_json(path)
            collected.extend(body["items"])
            cursor = body["next_cursor"]
            if cursor is None:
                break
        assert cursor is None, name
        epochs = [i["at_epoch"] for i in collected]
        assert epochs == sorted(epochs)
        assert epochs == [t.ut for t in tl.transitions], name
        before = [tl.meridian] + [t.utoff for t in tl.transitions[:-1]]
        assert [i["utoff_before"] for i in collected] == before, name


def test_transitions_range_filter(server, zones):
    tl = zones["Sable-Point"]
    lo, hi = tl.transitions[10].ut, tl.transitions[40].ut
    _, body = get_json("/v1/transitions?zone=Sable-Point&from=%d&to=%d&limit=1000" % (lo, hi))
    want = [t.ut for t in tl.transitions if lo <= t.ut <= hi]
    assert [i["at_epoch"] for i in body["items"]] == want


def test_tzif_endpoint_etag_and_304(server, zones):
    for name in zones:
        status, payload, headers = http_status("/v1/tzif/%s" % name)
        assert status == 200
        assert payload == zone_bytes(name), name
        etag = headers["etag"]
        assert etag == '"%s"' % hashlib.sha256(payload).hexdigest()
        status, _, _ = http_status("/v1/tzif/%s" % name, headers={"If-None-Match": etag})
        assert status == 304, name


def test_unknown_zone_404_and_bad_request_400(server, zones):
    assert http_status("/v1/tzif/Nowhere-Land")[0] == 404
    assert http_status("/v1/at?zone=Nowhere-Land&epoch=0")[0] == 404
    assert http_status("/v1/at?zone=Ossary-Fen")[0] == 400
    assert http_status("/v1/at?zone=Ossary-Fen&epoch=noon")[0] == 400
    assert http_status("/v1/transitions?zone=Ossary-Fen&limit=99999")[0] == 400
    assert http_status("/v1/resolve", method="POST",
                       body={"zone": "Ossary-Fen", "local": "not-a-time"})[0] == 400
    assert http_status("/v1/resolve", method="POST",
                       body={"zone": "Ossary-Fen", "local": "2000-01-01T00:00:00",
                             "policy": "guess"})[0] == 400


# ---------------------------------------------------------------------- cross-artifact
def test_manifest_db_etag_and_file_hashes_all_agree(db, server, zones):
    doc = {e["zone"]: e["sha256"] for e in json.loads(manifest())["zones"]}
    cur = db.cursor()
    cur.execute("SELECT zone, tzif_sha256 FROM zones")
    stored = dict(cur.fetchall())
    for name in zones:
        raw = zone_bytes(name)
        digest = hashlib.sha256(raw).hexdigest()
        _, payload, headers = http_status("/v1/tzif/%s" % name)
        assert digest == doc[name] == stored[name]
        assert headers["etag"] == '"%s"' % digest
        assert payload == raw
        assert digest == hashlib.sha256(civilref.serialize(zones[name])).hexdigest()
