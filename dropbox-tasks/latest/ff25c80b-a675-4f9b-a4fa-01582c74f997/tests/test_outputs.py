"""Verifier for library-consortium-net-checkouts-by-branch: run the agent pipeline
over the committed lake and require the net checkout count plus the per-branch split
and key intermediates to match the reference recomputed independently from the lake,
while every documented shortcut pipeline (monthly rollup, raw-UTC date filter, no
de-duplication, voided rows retained, first-ingest wins, status filtered before the
log is collapsed to the latest ingest, reading only the calendar-2024 slice, reading
only the delimited calendar-year slices while omitting the fixed-width migration
export, the catalog treated as one row per barcode, and the per-branch split left on
retired branch ids) lands a different figure and a hidden-seed lake defeats
hardcoding."""

import csv
import json
import os
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

APP = "/app"
ANSWER = os.path.join(APP, "answer.json")
FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

FY_START = "2024-07-01"
FY_END = "2025-06-30"
FY_TZ = ZoneInfo("America/Chicago")

CODES_FILE = "item_type_codes.csv"
CATALOG_FILE = "catalog_items.tsv"
XWALK_FILE = "branch_consolidations.csv"
# The per-event log is sliced by calendar year; fiscal year 2024 spans both slices.
LIVE_FILES = ["circ_transactions_2024.csv", "circ_transactions_2025.csv"]
# Circulation the replacement ILS owns after its mid-year cutover lives only in this
# fixed-width export, so the source of record is the union of the CSV slices and it.
MIGRATED_FILE = "circ_transactions_migrated.txt"
FWF_FIELDS = [
    ("txn_id", 10),
    ("barcode", 14),
    ("branch_id", 4),
    ("txn_type", 12),
    ("txn_ts", 20),
    ("status", 4),
    ("ingest_batch", 3),
]
ROLLUP_FILE = "circ_monthly_rollup.csv"


def _read(path, delim=","):
    """Read a delimited file into a list of dict rows."""
    with open(path, newline="") as f:
        return list(csv.DictReader(f, delimiter=delim))


def _read_fwf(path):
    """Parse the fixed-width migration export by character position into dict rows.

    Each field occupies a fixed range of columns with no delimiter; text fields are
    space-padded on the right, so each value is sliced by width and stripped. Parsed
    here with the standard library so it shares no machinery with the agent's
    readr-based fixed-width reader.
    """
    out = []
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            row = {}
            pos = 0
            for name, width in FWF_FIELDS:
                row[name] = line[pos : pos + width].strip()
                pos += width
            out.append(row)
    return out


def _local_date(ts):
    """Local (America/Chicago) calendar date of a UTC timestamp, as YYYY-MM-DD."""
    return (
        datetime.fromisoformat(ts.replace("Z", "+00:00"))
        .astimezone(FY_TZ)
        .strftime("%Y-%m-%d")
    )


def _latest_per_txn(rows):
    """Collapse rows to the highest ingest_batch per transaction id.

    The log is rebuilt by periodic sync batches and a later batch supersedes
    earlier copies of the same transaction id, so the authoritative copy of an
    event is the one carrying the largest ingest_batch.
    """
    latest = {}
    for e in rows:
        k = e["txn_id"]
        if k not in latest or int(e["ingest_batch"]) > int(latest[k]["ingest_batch"]):
            latest[k] = e
    return list(latest.values())


def _current_catalog(rows):
    """Collapse the catalog to the current record per barcode.

    The catalog is a periodic re-export that carries more than one row for a
    re-cataloged item, so the authoritative record is the one with the most recent
    record_updated date. Returns {barcode: current item_type_code}.
    """
    latest = {}
    for r in rows:
        bc = r["barcode"]
        if bc not in latest or r["record_updated"] > latest[bc]["record_updated"]:
            latest[bc] = r
    return {bc: int(r["item_type_code"]) for bc, r in latest.items()}


def _reference(lake_dir):
    """Independently recompute the net checkout count, by-branch split, and intermediates.

    The source of record is the union of the calendar-year CSV slices and the
    fixed-width migration export the replacement ILS owns after its mid-year cutover.
    It is collapsed to the latest ingest of each transaction id, then voided rows are
    dropped, per codebook.md. Fiscal year membership is decided on the local-time
    calendar date,
    recomputed here with the standard library zoneinfo so it does not share machinery
    with the agent's lubridate-based conversion. Adult nonfiction membership is taken
    from the current (most recently updated) catalog record per barcode, and the per
    branch split attributes retired branch ids to their surviving branch via the
    consolidation reference. Several shortcut pipelines (raw UTC date, no
    de-duplication, voided rows retained, first ingest wins, status filtered before
    the collapse, calendar-2024 slice only, monthly rollup, catalog not collapsed to
    the current record, per-branch split left on retired ids) are recomputed
    alongside to confirm each lands a different figure.
    """
    codes = {
        int(r["item_type_code"]): r["collection"]
        for r in _read(os.path.join(lake_dir, CODES_FILE))
    }
    catalog_rows = _read(os.path.join(lake_dir, CATALOG_FILE), delim="\t")
    catalog = _current_catalog(catalog_rows)
    xwalk = {
        r["retired_branch_id"]: r["surviving_branch_id"]
        for r in _read(os.path.join(lake_dir, XWALK_FILE))
    }

    csv_raw = []
    for fn in LIVE_FILES:
        csv_raw += _read(os.path.join(lake_dir, fn))
    migrated = _read_fwf(os.path.join(lake_dir, MIGRATED_FILE))
    raw = csv_raw + migrated
    raw_2024 = _read(os.path.join(lake_dir, "circ_transactions_2024.csv"))

    anf_items = {
        bc for bc, code in catalog.items() if codes.get(code) == "ADULT_NONFICTION"
    }
    # The catalog treated as one row per barcode: an item is taken as adult
    # nonfiction if any of its records is, instead of only its current record.
    anf_items_anyrow = {
        r["barcode"]
        for r in catalog_rows
        if codes.get(int(r["item_type_code"])) == "ADULT_NONFICTION"
    }

    def _branch(b):
        """Attribute a retired branch id to the surviving branch it merged into."""
        return xwalk.get(b, b)

    # Latest ingest per transaction id. n_events_fy2024 counts these distinct events
    # of any type in the fiscal year regardless of status; the checkout answer
    # additionally drops the voided rows.
    deduped = _latest_per_txn(raw)
    clean = [e for e in deduped if e["status"] == "OK"]

    # Distinct fiscal-year-2024 circulation events of any type over the collapsed log.
    n_events_fy = sum(
        1 for e in deduped if FY_START <= _local_date(e["txn_ts"]) <= FY_END
    )

    answer = 0
    n_renew = 0
    by_branch = {}
    by_branch_unmapped = {}
    # The disclosed-default pipeline compares the raw UTC date string instead of
    # converting to local time; it is recomputed alongside to confirm it is wrong.
    answer_utcstring = 0
    for e in clean:
        d = _local_date(e["txn_ts"])
        is_anf = e["barcode"] in anf_items
        if FY_START <= d <= FY_END:
            if is_anf and e["txn_type"] == "CHECKOUT":
                answer += 1
                b = _branch(e["branch_id"])
                by_branch[b] = by_branch.get(b, 0) + 1
                rb = e["branch_id"]
                by_branch_unmapped[rb] = by_branch_unmapped.get(rb, 0) + 1
            if is_anf and e["txn_type"] == "RENEW":
                n_renew += 1
        if FY_START <= e["txn_ts"][:10] <= FY_END:
            if is_anf and e["txn_type"] == "CHECKOUT":
                answer_utcstring += 1

    def _anf_checkouts_fy(events, anf_set):
        """Adult-nonfiction CHECKOUT count in fiscal year 2024 over an event list."""
        return sum(
            1
            for e in events
            if e["barcode"] in anf_set
            and e["txn_type"] == "CHECKOUT"
            and FY_START <= _local_date(e["txn_ts"]) <= FY_END
        )

    # Skipping de-duplication keeps every re-ingested row. Retaining voided rows
    # keeps reversed transactions. Both overcount the answer.
    answer_with_dups = _anf_checkouts_fy(
        [e for e in raw if e["status"] == "OK"], anf_items
    )
    answer_with_void = _anf_checkouts_fy(_latest_per_txn(raw), anf_items)

    # Keeping the first ingest of each transaction id instead of the latest ignores
    # the status corrections carried by later batches.
    first = {}
    for e in raw:
        k = e["txn_id"]
        if k not in first or int(e["ingest_batch"]) < int(first[k]["ingest_batch"]):
            first[k] = e
    answer_firstingest = _anf_checkouts_fy(
        [e for e in first.values() if e["status"] == "OK"], anf_items
    )

    # Filtering on OK status before collapsing the log keeps an earlier OK copy of a
    # transaction whose latest ingest corrected it to VOID.
    ok_first = {}
    for e in raw:
        if e["status"] == "OK":
            ok_first.setdefault(e["txn_id"], e)
    answer_statusbeforededup = _anf_checkouts_fy(list(ok_first.values()), anf_items)

    # Reading only the calendar-2024 slice drops the January-June 2025 half of the
    # fiscal year, even with an otherwise-correct pipeline.
    answer_single_slice = _anf_checkouts_fy(
        [e for e in _latest_per_txn(raw_2024) if e["status"] == "OK"], anf_items
    )

    # Reading only the delimited calendar-year slices omits the fixed-width migration
    # export the replacement ILS owns after its mid-year cutover, dropping the
    # post-cutover circulation and undercounting.
    answer_csv_only = _anf_checkouts_fy(
        [e for e in _latest_per_txn(csv_raw) if e["status"] == "OK"], anf_items
    )

    # Treating the catalog as one row per barcode counts items that were re-cataloged
    # out of adult nonfiction but still carry an older adult nonfiction record.
    answer_catalog_anyrow = _anf_checkouts_fy(clean, anf_items_anyrow)

    rollup = _read(os.path.join(lake_dir, ROLLUP_FILE))
    naive_rollup = sum(
        int(r["checkouts_total"])
        for r in rollup
        if FY_START[:7] <= r["month"] <= FY_END[:7]
    )

    return {
        "answer": answer,
        "by_branch": by_branch,
        "by_branch_unmapped": by_branch_unmapped,
        "n_events_fy2024": n_events_fy,
        "n_renewals_excluded": n_renew,
        "n_adult_nonfiction_items": len(anf_items),
        "n_adult_nonfiction_items_anyrow": len(anf_items_anyrow),
        "naive_rollup": naive_rollup,
        "answer_utcstring": answer_utcstring,
        "answer_with_dups": answer_with_dups,
        "answer_with_void": answer_with_void,
        "answer_firstingest": answer_firstingest,
        "answer_statusbeforededup": answer_statusbeforededup,
        "answer_single_slice": answer_single_slice,
        "answer_csv_only": answer_csv_only,
        "answer_catalog_anyrow": answer_catalog_anyrow,
    }


def _run_agent(lake_dir):
    """Run the agent R pipeline against a lake directory via the DATALAKE_DIR override."""
    env = dict(os.environ, DATALAKE_DIR=lake_dir)
    r = subprocess.run(
        ["Rscript", os.path.join(APP, "analysis.R")],
        cwd=APP,
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert r.returncode == 0, r.stderr
    with open(ANSWER) as f:
        return json.load(f)


def _imap(m):
    """Coerce a JSON object of branch counts to a plain int-valued dict."""
    return {str(k): int(v) for k, v in m.items()}


def test_output_schema():
    """answer.json carries the count, the by-branch map, and the intermediate fields."""
    out = _run_agent(os.path.join(APP, "data"))
    for key in [
        "answer",
        "n_events_fy2024",
        "n_renewals_excluded",
        "n_adult_nonfiction_items",
    ]:
        assert key in out and float(out[key]) == int(out[key])
    assert isinstance(out["by_branch"], dict) and len(out["by_branch"]) >= 1


def test_final_answer_matches():
    """The net checkout count and per-branch split match the reference recomputed from the lake.

    The agent pipeline is run on the committed lake here rather than trusting a
    possibly hand-edited answer.json, so a hardcoded answer cannot pass.
    """
    out = _run_agent(os.path.join(APP, "data"))
    ref = _reference(os.path.join(APP, "data"))
    assert int(out["answer"]) == ref["answer"]
    assert _imap(out["by_branch"]) == ref["by_branch"]


def test_by_branch_sums_to_answer():
    """The per-branch split is internally consistent: its values sum to the headline count."""
    out = _run_agent(os.path.join(APP, "data"))
    assert sum(_imap(out["by_branch"]).values()) == int(out["answer"])


def test_intermediates_match():
    """The key intermediate facts match the reference, catching right-answer-by-wrong-path."""
    out = _run_agent(os.path.join(APP, "data"))
    ref = _reference(os.path.join(APP, "data"))
    assert int(out["n_events_fy2024"]) == ref["n_events_fy2024"]
    assert int(out["n_renewals_excluded"]) == ref["n_renewals_excluded"]
    assert int(out["n_adult_nonfiction_items"]) == ref["n_adult_nonfiction_items"]


def test_no_forbidden_access():
    """The agent pipeline does not read the verifier tree or hardcode the answer."""
    with open(os.path.join(APP, "analysis.R")) as f:
        src = f.read()
    assert "/tests" not in src


def test_naive_pipeline_fails():
    """The pre-aggregated monthly rollup yields a count outside the answer."""
    ref = _reference(os.path.join(APP, "data"))
    assert ref["naive_rollup"] != ref["answer"]
    assert abs(ref["naive_rollup"] - ref["answer"]) > 0.01 * ref["answer"]


def test_disclosed_default_fails():
    """Filtering on the raw UTC date instead of local time gives the wrong count.

    The fiscal window is defined in local time while timestamps are stored in UTC,
    so a pipeline that compares the UTC date string lands a body of boundary events
    on the wrong side of the window and cannot reproduce the answer.
    """
    ref = _reference(os.path.join(APP, "data"))
    assert ref["answer_utcstring"] != ref["answer"]
    assert abs(ref["answer_utcstring"] - ref["answer"]) > 0.01 * ref["answer"]


def test_skipping_dedup_fails():
    """Counting the log without de-duplicating on the transaction id overcounts.

    The source of record is re-ingested by replayed nightly syncs, so a transaction
    id can appear on more than one row. A pipeline that counts every row instead of
    one row per transaction id lands a checkout count above the answer.
    """
    ref = _reference(os.path.join(APP, "data"))
    assert ref["answer_with_dups"] != ref["answer"]
    assert abs(ref["answer_with_dups"] - ref["answer"]) > 0.01 * ref["answer"]


def test_keeping_voided_rows_fails():
    """Retaining VOID-status rows overcounts the answer.

    Voided transactions were reversed at the desk and never represented a real
    circulation, so a pipeline that keeps them counts checkouts that did not happen
    and cannot reproduce the answer.
    """
    ref = _reference(os.path.join(APP, "data"))
    assert ref["answer_with_void"] != ref["answer"]
    assert abs(ref["answer_with_void"] - ref["answer"]) > 0.01 * ref["answer"]


def test_first_ingest_wins_fails():
    """Keeping the first ingest of each transaction id instead of the latest gives the wrong count.

    A later sync batch supersedes earlier copies of a transaction id and can correct
    its status. A pipeline that keeps the first row per transaction id ignores those
    corrections and reproduces neither the checkouts that were reversed after the
    fact nor the ones that were reinstated.
    """
    ref = _reference(os.path.join(APP, "data"))
    assert ref["answer_firstingest"] != ref["answer"]
    assert abs(ref["answer_firstingest"] - ref["answer"]) > 0.01 * ref["answer"]


def test_status_filtered_before_collapse_fails():
    """Dropping VOID rows before collapsing the log to the latest ingest overcounts.

    When a checkout is corrected from OK to VOID by a later batch, an earlier OK copy
    of the same transaction id survives a status filter that runs before the log is
    reduced to one row per transaction id, so the reversed checkout is counted anyway.
    """
    ref = _reference(os.path.join(APP, "data"))
    assert ref["answer_statusbeforededup"] != ref["answer"]
    assert abs(ref["answer_statusbeforededup"] - ref["answer"]) > 0.01 * ref["answer"]


def test_single_slice_fails():
    """Reading only the calendar-2024 slice misses the second half of the fiscal year.

    Fiscal year 2024 runs into June 2025, whose events live in the calendar-2025
    slice. A pipeline that reads only the slice whose name matches the fiscal-year
    label silently drops half the window and undercounts.
    """
    ref = _reference(os.path.join(APP, "data"))
    assert ref["answer_single_slice"] != ref["answer"]
    assert abs(ref["answer_single_slice"] - ref["answer"]) > 0.01 * ref["answer"]


def test_missing_migration_slice_fails():
    """Reading only the delimited slices, omitting the fixed-width migration export, undercounts.

    The replacement ILS owns circulation after its mid-year cutover and exports it
    only to the fixed-width migration file, so a pipeline that reads only the
    calendar-year CSV slices (including one that globs circ_transactions_*.csv) drops
    the entire post-cutover block and cannot reproduce the answer.
    """
    ref = _reference(os.path.join(APP, "data"))
    assert ref["answer_csv_only"] != ref["answer"]
    assert abs(ref["answer_csv_only"] - ref["answer"]) > 0.01 * ref["answer"]


def test_catalog_not_collapsed_fails():
    """Treating the catalog as one row per barcode overcounts adult nonfiction.

    The catalog carries more than one row for a re-cataloged item, and an item's
    current collection is the one on its most recently updated record. A pipeline
    that calls an item adult nonfiction because any of its records is keeps items
    that were re-cataloged out of the collection, inflating both the item count and
    the checkout count.
    """
    ref = _reference(os.path.join(APP, "data"))
    assert ref["answer_catalog_anyrow"] != ref["answer"]
    assert abs(ref["answer_catalog_anyrow"] - ref["answer"]) > 0.01 * ref["answer"]
    assert ref["n_adult_nonfiction_items_anyrow"] != ref["n_adult_nonfiction_items"]


def test_unmapped_branches_fails():
    """Leaving the per-branch split on raw branch ids reports phantom retired branches.

    Some events are recorded under retired branch ids that merged into a surviving
    branch. A split that groups on the raw branch id reports branches that no longer
    exist and misattributes their circulation, so it cannot match the reference.
    """
    ref = _reference(os.path.join(APP, "data"))
    assert ref["by_branch_unmapped"] != ref["by_branch"]
    retired = set(ref["by_branch_unmapped"]) - set(ref["by_branch"])
    assert retired


def test_hidden_lake_generalizes():
    """Re-running the agent pipeline on a hidden-seed lake reproduces the recomputed answer."""
    hidden = os.path.join(FIX, "lake_hidden")
    out = _run_agent(hidden)
    ref = _reference(hidden)
    assert int(out["answer"]) == ref["answer"]
    assert _imap(out["by_branch"]) == ref["by_branch"]
    assert int(out["n_events_fy2024"]) == ref["n_events_fy2024"]
    assert int(out["n_renewals_excluded"]) == ref["n_renewals_excluded"]
    assert int(out["n_adult_nonfiction_items"]) == ref["n_adult_nonfiction_items"]
