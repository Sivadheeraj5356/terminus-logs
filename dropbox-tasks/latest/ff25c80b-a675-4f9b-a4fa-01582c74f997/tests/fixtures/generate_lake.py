"""Deterministic generator for the library-consortium-net-checkouts-by-branch lake.

Author-side / verifier-side only. Never copied into the agent image and never run
by tests/test.sh. Emits a 37 file lake (two calendar-year CSV slices and one
fixed-width migration export that are authoritative, plus decoys) from a fixed
integer seed, so the committed lake (seed A) and the hidden lake (seed B) come from
one code path. Usage:

    python3 generate_lake.py <seed> <out_dir>

Conventions baked in here and mirrored by the codebook, the R oracle, and the Python
reference verifier:
  - fiscal year 2024 spans 2024-07-01 through 2025-06-30 inclusive, in the
    consortium's local time zone America/Chicago
  - transactional timestamps are recorded in UTC (trailing Z); fiscal year
    membership is decided after converting each timestamp to local time
  - the per-event transactional log is exported in calendar-year slices
    (circ_transactions_2024.csv holds calendar 2024, circ_transactions_2025.csv
    holds calendar 2025); fiscal year 2024 draws from both slices, so the source
    of record is the union of the slices, restricted to the fiscal window by the
    local date of each event
  - txn_type in {CHECKOUT, RENEW, RETURN, HOLD_FILLED}; a net checkout is a CHECKOUT
  - each event carries a status of OK or VOID; a VOID row was reversed at the desk
    and never represented a real circulation, so voided rows are excluded from
    every figure
  - the log is rebuilt by periodic sync batches recorded in ingest_batch; a later
    batch supersedes earlier copies of the same transaction id, including
    corrections to its status (OK->VOID and VOID->OK), so the log must be reduced
    to the highest ingest_batch per transaction id BEFORE the status filter is
    applied
  - the item catalog is a periodic re-export and carries more than one row for an
    item that has been re-cataloged; each row records the date its record was last
    updated, a later record supersedes an earlier one for the same barcode, and a
    re-catalog can move an item between item type codes, so an item's current item
    type is the one on its most recently updated record
  - collection membership is resolved through the item type code reference, against
    the item's current item type
  - some events carry a retired branch id from before a branch consolidation; a
    consolidation reference maps each retired id to the surviving branch it merged
    into, and circulation under a retired id belongs to that surviving branch
  - barcodes are 14 character zero padded strings and must be read as text
  - the monthly rollup is a convenience export that folds renewals into its counts
    and carries no item or collection detail

A block of live events is placed in the early UTC hours of the two fiscal
boundary days (2024-07-01 and 2025-07-01). At both boundaries local time is
CDT (UTC-5), so a UTC instant before 05:00 falls on the previous local day.
Those events flip across the fiscal window when timestamps are interpreted in
local time rather than compared as raw UTC date strings, which is what makes a
UTC-string filter produce the wrong figure.

Several further conventions are layered on top so that a pipeline which is correct
on time zone, collection, and event type can still land the wrong figure:

  - The window-correctness trap: fiscal year 2024 spans two calendar-year slice
    files. A pipeline that reads only circ_transactions_2024.csv (the slice whose
    name matches the fiscal year label) silently drops the entire January-June
    2025 half of the fiscal year.

  - The supersede trap: a block of transactions is re-ingested by a later sync
    batch that corrects the status of the event. Some checkouts are corrected
    from OK to VOID (the circulation was reversed after the original sync) and
    some from VOID to OK (a desk void was itself undone). The authoritative state
    is the highest ingest_batch per transaction id. A pipeline that keeps the
    first row per transaction id, or that filters out VOID rows before collapsing
    to the latest copy, lands the wrong figure.

  - The duplicate trap: a further block of rows is re-ingested verbatim (same
    transaction id, identical content, a later batch number) so the log must be
    de-duplicated on the transaction id. A pipeline that counts every row instead
    of one row per transaction id overcounts.

  - The re-catalog trap: the catalog carries more than one row for a re-cataloged
    item, and a re-catalog can move the item between collections. A block of adult
    nonfiction items is re-cataloged into other collections (and a smaller block
    the other way). A pipeline that treats the catalog as one row per barcode, or
    that calls an item adult nonfiction because any of its rows is, counts items
    that are no longer adult nonfiction.

  - The branch-consolidation trap: a block of events is recorded under retired
    branch ids that are not present in branches.csv. A consolidation reference
    maps each retired id to a surviving branch. A pipeline that groups on the raw
    branch id reports phantom branches and misattributes their circulation.

  - The migration-slice trap: a block of fiscal-year circulation lives only in a
    fixed-width export from the replacement ILS the consortium cut over to partway
    through the year, not in the calendar-year CSV slices. A pipeline that reads
    only the CSV slices (including one that globs circ_transactions_*.csv) misses
    the post-cutover circulation and undercounts, and the fixed-width layout has to
    be parsed by character position with the barcode kept as text.

The window, supersede, duplicate, and re-catalog blocks each reach into fiscal year
2024 and into the adult nonfiction checkout count by enough margin that a pipeline
which skips any one step misses the answer by well over one percent; the
consolidation block shifts the per branch split.
"""

import csv
import datetime
import json
import os
import random
import sys
from zoneinfo import ZoneInfo

FY_TZ = ZoneInfo("America/Chicago")

BRANCHES = ["B%02d" % i for i in range(1, 10)]

CODE_MAP = [
    (100, "ADULT_NONFICTION", "Adult nonfiction print"),
    (101, "ADULT_NONFICTION", "Adult nonfiction reference"),
    (102, "ADULT_NONFICTION", "Adult nonfiction large print"),
    (110, "ADULT_FICTION", "Adult fiction print"),
    (111, "ADULT_FICTION", "Adult fiction large print"),
    (200, "JUVENILE", "Juvenile print"),
    (201, "JUVENILE", "Juvenile easy reader"),
    (300, "PERIODICAL", "Periodical issue"),
    (400, "MEDIA", "Audiovisual media"),
    (401, "MEDIA", "Playaway media"),
]
CODES = [c[0] for c in CODE_MAP]
CODE_WEIGHTS = [0.12, 0.07, 0.06, 0.18, 0.05, 0.16, 0.10, 0.08, 0.10, 0.08]
ANF_CODES = {code for code, coll, _ in CODE_MAP if coll == "ADULT_NONFICTION"}
NONANF_CODES = [code for code, coll, _ in CODE_MAP if coll != "ADULT_NONFICTION"]

TXN_TYPES = ["CHECKOUT", "RENEW", "RETURN", "HOLD_FILLED"]
TXN_WEIGHTS = [0.50, 0.25, 0.20, 0.05]

# A status of VOID marks a desk-reversed transaction that never represented a
# real circulation; voided rows are excluded from every figure.
TXN_STATUS = ["OK", "VOID"]
TXN_STATUS_WEIGHTS = [0.96, 0.04]

N_ITEMS = 8000
N_LIVE = 90000
N_ARCHIVE = 40000

# Rows re-ingested verbatim (same transaction id, later batch) by a replayed
# nightly sync. They must be de-duplicated on the transaction id before counting.
N_DUP = 6000

# Transactions re-ingested by a later batch with a corrected status. The latest
# batch is authoritative, so the log must be collapsed to the highest ingest_batch
# per transaction id before the status filter is applied. Both blocks are drawn
# from fiscal-year adult-nonfiction checkouts so they move the answer.
N_VOID_CORR = 1500  # checkouts corrected OK -> VOID by a later batch
N_UNVOID_CORR = 600  # checkouts corrected VOID -> OK (capped by supply)

# Items re-cataloged into a different collection by a later catalog export. The
# current item type is the one on the most recently updated record, so an item
# re-cataloged out of adult nonfiction is no longer adult nonfiction even though
# an earlier record still says it was.
N_RECAT_OUT = 220  # adult nonfiction items re-cataloged into another collection
N_RECAT_IN = 140  # items re-cataloged into adult nonfiction from elsewhere

# Circulation migrated to a replacement integrated library system partway through
# the fiscal year. The new system exports its events as a fixed-width text file,
# and these events are NOT repeated in the calendar-year CSV slices, so the source
# of record for the fiscal year is the union of the CSV slices and this export. The
# block is weighted like the rest of the log (so a healthy share are fiscal-year
# adult-nonfiction checkouts) and confined to the fiscal-year interior, so a
# pipeline that reads only the CSV slices undercounts by well over one percent.
N_MIGRATED = 5200
MIGRATED_START = "2025-02-01"  # ILS cutover; the new system owns circulation after this
MIGRATED_END = "2025-06-29"

# Fixed-width layout of circ_transactions_migrated.txt: (field, width). Text fields
# are left-justified and space-padded; the file carries no delimiter, so it must be
# parsed by character position. Mirrored by the codebook, the R oracle, and the
# Python reference verifier.
FWF_FIELDS = [
    ("txn_id", 10),
    ("barcode", 14),
    ("branch_id", 4),
    ("txn_type", 12),
    ("txn_ts", 20),
    ("status", 4),
    ("ingest_batch", 3),
]

# Events recorded under retired branch ids that were merged into a surviving
# branch. They are confined to the fiscal-year interior and to adult nonfiction
# items so they land in the per-branch split once attributed to the survivor.
N_RETIRED = 900
RETIRED_MAP = [
    ("B91", "B02", "2023-09-30"),
    ("B92", "B05", "2022-06-30"),
    ("B93", "B08", "2024-01-31"),
]

FY_START = "2024-07-01"
FY_END = "2025-06-30"

# Live events placed in the [00:00, 05:00) UTC flip zone of each boundary day.
# At UTC-5 (CDT) these all roll back to the previous local day, so a UTC-string
# filter classifies them on the wrong side of the fiscal window. The two blocks
# are deliberately asymmetric so the net miscount does not cancel out.
FLIP_BLOCKS = [
    (5000, datetime.datetime(2024, 7, 1, 0, 0, 0)),
    (2000, datetime.datetime(2025, 7, 1, 0, 0, 0)),
]
FLIP_ZONE_MINUTES = 5 * 60

LIVE_HEADER = [
    "txn_id",
    "barcode",
    "branch_id",
    "txn_type",
    "txn_ts",
    "status",
    "ingest_batch",
]

CATALOG_HEADER = [
    "barcode",
    "item_type_code",
    "title",
    "acquired_date",
    "record_updated",
]


def _local_date(ts):
    return (
        datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        .astimezone(FY_TZ)
        .strftime("%Y-%m-%d")
    )


def _rand_date(rng, start, end):
    a = datetime.date.fromisoformat(start).toordinal()
    b = datetime.date.fromisoformat(end).toordinal()
    return datetime.date.fromordinal(rng.randint(a, b)).isoformat()


def _ts(rng, date_str):
    return "%sT%02d:%02d:%02dZ" % (
        date_str,
        rng.randint(0, 23),
        rng.randint(0, 59),
        rng.randint(0, 59),
    )


def _interior_ts(rng, date_str):
    """A UTC timestamp at midday so its local date equals its UTC date. Used for
    events that must sit unambiguously inside the fiscal window."""
    return "%sT%02d:%02d:%02dZ" % (
        date_str,
        rng.randint(12, 22),
        rng.randint(0, 59),
        rng.randint(0, 59),
    )


def _write_csv(path, rows, header, delim=","):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header, delimiter=delim, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _write_json(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, indent=1)


def _build_catalog(rng, barcodes):
    """Build the catalog as a re-export that carries more than one row for some
    barcodes. Returns (catalog_records, auth_code) where auth_code[bc] is the item
    type on the most recently updated record, i.e. the item's current item type."""
    base_code = {}
    acquired = {}
    records = []
    for bc in barcodes:
        code = rng.choices(CODES, weights=CODE_WEIGHTS, k=1)[0]
        base_code[bc] = code
        acq = _rand_date(rng, "2008-01-01", "2024-06-30")
        acquired[bc] = acq
        records.append(
            {
                "barcode": bc,
                "item_type_code": code,
                "title": "Title %s" % bc[-6:],
                "acquired_date": acq,
                "record_updated": _rand_date(rng, "2015-01-01", "2022-12-31"),
            }
        )

    auth_code = dict(base_code)
    base_anf = [bc for bc in barcodes if base_code[bc] in ANF_CODES]
    base_nonanf = [bc for bc in barcodes if base_code[bc] not in ANF_CODES]

    def _recat(bc, new_code):
        records.append(
            {
                "barcode": bc,
                "item_type_code": new_code,
                "title": "Title %s" % bc[-6:],
                "acquired_date": acquired[bc],
                "record_updated": _rand_date(rng, "2023-06-01", "2024-12-31"),
            }
        )
        auth_code[bc] = new_code

    for bc in rng.sample(base_anf, N_RECAT_OUT):
        _recat(bc, rng.choice(NONANF_CODES))
    for bc in rng.sample(base_nonanf, N_RECAT_IN):
        _recat(bc, rng.choice(sorted(ANF_CODES)))

    return records, auth_code


def generate(seed, out_dir):
    rng = random.Random(seed)
    os.makedirs(out_dir, exist_ok=True)

    item_codes = [
        {"item_type_code": code, "collection": coll, "description": desc}
        for code, coll, desc in CODE_MAP
    ]
    _write_csv(
        os.path.join(out_dir, "item_type_codes.csv"),
        item_codes,
        ["item_type_code", "collection", "description"],
    )

    barcodes = ["%014d" % i for i in range(1, N_ITEMS + 1)]
    catalog, auth_code = _build_catalog(rng, barcodes)
    _write_csv(
        os.path.join(out_dir, "catalog_items.tsv"),
        catalog,
        CATALOG_HEADER,
        delim="\t",
    )

    # The authoritative adult nonfiction set is decided on the current item type.
    anf_barcodes = {bc for bc in barcodes if auth_code[bc] in ANF_CODES}

    n_flip = sum(n for n, _ in FLIP_BLOCKS)
    live = _make_events(rng, barcodes, N_LIVE - n_flip, "2024-01-01", "2025-12-31", "T")
    live += _make_flip_events(rng, barcodes, len(live), FLIP_BLOCKS)

    live += _ingest_corrections(rng, live, anf_barcodes)
    live += _replay_duplicates(rng, live, anf_barcodes, N_DUP)
    live += _make_retired_branch_events(rng, sorted(anf_barcodes), len(live), N_RETIRED)

    # Circulation the replacement ILS owns after the mid-year cutover. It is emitted
    # only to the fixed-width export, never to the CSV slices, so a fiscal-year
    # figure has to union it in.
    migrated = _make_migrated_events(rng, barcodes, N_MIGRATED)
    _write_fwf(
        os.path.join(out_dir, "circ_transactions_migrated.txt"), migrated, FWF_FIELDS
    )

    # Slice the per-event log by the calendar year of the (UTC) timestamp. Fiscal
    # year 2024 spans both slices; a correction or duplicate keeps the original
    # timestamp, so it lands in the same slice as the row it supersedes.
    slice_2024 = [e for e in live if e["txn_ts"][:4] == "2024"]
    slice_2025 = [e for e in live if e["txn_ts"][:4] == "2025"]
    _write_csv(
        os.path.join(out_dir, "circ_transactions_2024.csv"), slice_2024, LIVE_HEADER
    )
    _write_csv(
        os.path.join(out_dir, "circ_transactions_2025.csv"), slice_2025, LIVE_HEADER
    )

    _write_csv(
        os.path.join(out_dir, "branch_consolidations.csv"),
        [
            {
                "retired_branch_id": rid,
                "surviving_branch_id": sid,
                "merged_on": when,
            }
            for rid, sid, when in RETIRED_MAP
        ],
        ["retired_branch_id", "surviving_branch_id", "merged_on"],
    )

    _build_decoys(rng, out_dir, barcodes, live)


def _make_events(rng, barcodes, n, start, end, prefix):
    out = []
    for i in range(1, n + 1):
        d = _rand_date(rng, start, end)
        out.append(
            {
                "txn_id": "%s%07d" % (prefix, i),
                "barcode": rng.choice(barcodes),
                "branch_id": rng.choice(BRANCHES),
                "txn_type": rng.choices(TXN_TYPES, weights=TXN_WEIGHTS, k=1)[0],
                "txn_ts": _ts(rng, d),
                "status": rng.choices(TXN_STATUS, weights=TXN_STATUS_WEIGHTS, k=1)[0],
                "ingest_batch": 1,
            }
        )
    return out


def _make_flip_events(rng, barcodes, start_index, blocks):
    out = []
    i = start_index
    for n, base in blocks:
        for _ in range(n):
            i += 1
            offset = rng.randint(0, FLIP_ZONE_MINUTES * 60 - 1)
            dt = base + datetime.timedelta(seconds=offset)
            out.append(
                {
                    "txn_id": "T%07d" % i,
                    "barcode": rng.choice(barcodes),
                    "branch_id": rng.choice(BRANCHES),
                    "txn_type": rng.choices(TXN_TYPES, weights=TXN_WEIGHTS, k=1)[0],
                    "txn_ts": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "status": rng.choices(TXN_STATUS, weights=TXN_STATUS_WEIGHTS, k=1)[
                        0
                    ],
                    "ingest_batch": 1,
                }
            )
    return out


def _make_retired_branch_events(rng, anf_barcodes_list, start_index, n):
    """Adult-nonfiction events recorded under retired branch ids inside the
    fiscal-year interior. Their checkouts count toward the answer once attributed,
    and they define the per-branch split's consolidation trap."""
    retired_ids = [rid for rid, _, _ in RETIRED_MAP]
    out = []
    i = start_index
    for _ in range(n):
        i += 1
        d = _rand_date(rng, "2024-07-02", "2025-06-29")
        out.append(
            {
                "txn_id": "Z%07d" % i,
                "barcode": rng.choice(anf_barcodes_list),
                "branch_id": rng.choice(retired_ids),
                "txn_type": rng.choices(TXN_TYPES, weights=TXN_WEIGHTS, k=1)[0],
                "txn_ts": _interior_ts(rng, d),
                "status": rng.choices(TXN_STATUS, weights=TXN_STATUS_WEIGHTS, k=1)[0],
                "ingest_batch": 1,
            }
        )
    return out


def _make_migrated_events(rng, barcodes, n):
    """Circulation captured only by the replacement ILS after its mid-year cutover.

    Emitted to the fixed-width export rather than the CSV slices, with interior
    timestamps that keep the block clear of the time-zone boundary so it is a pure
    source-of-record-completeness trap. Transaction ids carry an M prefix and never
    appear in the CSV slices, so the union de-duplicates cleanly."""
    out = []
    for i in range(1, n + 1):
        d = _rand_date(rng, MIGRATED_START, MIGRATED_END)
        out.append(
            {
                "txn_id": "M%07d" % i,
                "barcode": rng.choice(barcodes),
                "branch_id": rng.choice(BRANCHES),
                "txn_type": rng.choices(TXN_TYPES, weights=TXN_WEIGHTS, k=1)[0],
                "txn_ts": _interior_ts(rng, d),
                "status": rng.choices(TXN_STATUS, weights=TXN_STATUS_WEIGHTS, k=1)[0],
                "ingest_batch": 1,
            }
        )
    return out


def _write_fwf(path, rows, fields):
    """Write rows as fixed-width text: each field left-justified in its width, no
    delimiter, one row per line. Field content never exceeds its width."""
    with open(path, "w") as f:
        for r in rows:
            f.write("".join("%-*s" % (w, str(r[name])) for name, w in fields) + "\n")


def _fy_anf_checkout(e, anf_barcodes, status):
    return (
        e["barcode"] in anf_barcodes
        and e["txn_type"] == "CHECKOUT"
        and e["status"] == status
        and FY_START <= _local_date(e["txn_ts"]) <= FY_END
    )


def _supersede(row, status):
    """A later-batch copy of a transaction with a corrected status."""
    new = dict(row)
    new["status"] = status
    new["ingest_batch"] = 2
    return new


def _ingest_corrections(rng, live, anf_barcodes):
    """Re-ingest a block of fiscal-year adult-nonfiction checkouts with a corrected
    status in a later batch. The highest ingest_batch per transaction id is
    authoritative, so these flip whether the event counts once the log is
    collapsed to the latest copy."""
    ok_targets = [e for e in live if _fy_anf_checkout(e, anf_barcodes, "OK")]
    void_targets = [e for e in live if _fy_anf_checkout(e, anf_barcodes, "VOID")]
    void_corr = rng.sample(ok_targets, N_VOID_CORR)
    unvoid_corr = rng.sample(void_targets, min(N_UNVOID_CORR, len(void_targets)))
    out = [_supersede(r, "VOID") for r in void_corr]
    out += [_supersede(r, "OK") for r in unvoid_corr]
    return out


def _replay_duplicates(rng, live, anf_barcodes, n_dup):
    """Re-ingest a sample of rows verbatim in a later batch, simulating a replayed
    nightly sync. Each returned row reuses an existing transaction id with
    identical content, so the log carries the same event on more than one row and
    must be de-duplicated on the transaction id before any figure is computed.

    Rows already chosen for a status correction are excluded so a transaction id
    never carries two conflicting copies at the same batch number."""
    corrected = {e["txn_id"] for e in live if e["ingest_batch"] == 2}
    pool = [e for e in live if e["ingest_batch"] == 1 and e["txn_id"] not in corrected]
    out = []
    for row in rng.sample(pool, n_dup):
        dup = dict(row)
        dup["ingest_batch"] = 2
        out.append(dup)
    return out


def _build_decoys(rng, out_dir, barcodes, live):
    archive = _make_events(rng, barcodes, N_ARCHIVE, "2022-01-01", "2023-12-31", "A")
    _write_csv(
        os.path.join(out_dir, "circ_transactions_2023.csv"),
        archive,
        LIVE_HEADER,
    )

    rollup = {}
    for e in live:
        if e["ingest_batch"] == 1 and e["txn_type"] in ("CHECKOUT", "RENEW"):
            key = (e["txn_ts"][:7], e["branch_id"])
            rollup[key] = rollup.get(key, 0) + 1
    rollup_rows = [
        {"month": m, "branch_id": b, "checkouts_total": n}
        for (m, b), n in sorted(rollup.items())
    ]
    _write_csv(
        os.path.join(out_dir, "circ_monthly_rollup.csv"),
        rollup_rows,
        ["month", "branch_id", "checkouts_total"],
    )

    sample = []
    for i in range(1, 201):
        sample.append(
            {
                "txn_id": "SMPL%05d" % i,
                "barcode": "SAMPLE%08d" % i,
                "branch_id": rng.choice(BRANCHES),
                "txn_type": rng.choice(TXN_TYPES),
                "txn_ts": _ts(rng, _rand_date(rng, "2024-07-01", "2025-06-30")),
                "status": rng.choice(TXN_STATUS),
            }
        )
    _write_csv(
        os.path.join(out_dir, "circ_sample_vendor.csv"),
        sample,
        ["txn_id", "barcode", "branch_id", "txn_type", "txn_ts", "status"],
    )

    _write_csv(
        os.path.join(out_dir, "branches.csv"),
        [
            {
                "branch_id": b,
                "branch_name": "Branch %s" % b[1:],
                "region": rng.choice(["NORTH", "SOUTH", "EAST", "WEST"]),
            }
            for b in BRANCHES
        ],
        ["branch_id", "branch_name", "region"],
    )

    patron_ids = ["P%06d" % i for i in range(1, 6001)]
    _write_csv(
        os.path.join(out_dir, "patrons.csv"),
        [
            {
                "patron_id": p,
                "home_branch": rng.choice(BRANCHES),
                "patron_type": rng.choice(["ADULT", "JUVENILE", "SENIOR", "STAFF"]),
                "registered": _rand_date(rng, "2010-01-01", "2025-01-01"),
            }
            for p in patron_ids
        ],
        ["patron_id", "home_branch", "patron_type", "registered"],
    )

    _write_json(
        os.path.join(out_dir, "holds.json"),
        [
            {
                "hold_id": "H%06d" % i,
                "barcode": rng.choice(barcodes),
                "patron_id": rng.choice(patron_ids),
                "status": rng.choice(["ACTIVE", "FILLED", "CANCELLED"]),
            }
            for i in range(1, 1201)
        ],
    )

    _write_csv(
        os.path.join(out_dir, "fines.csv"),
        [
            {
                "fine_id": "FN%06d" % i,
                "patron_id": rng.choice(patron_ids),
                "amount_usd": "%.2f" % rng.uniform(0.25, 35.0),
                "reason": rng.choice(["OVERDUE", "DAMAGE", "LOST"]),
            }
            for i in range(1, 2001)
        ],
        ["fine_id", "patron_id", "amount_usd", "reason"],
    )

    legacy_path = os.path.join(out_dir, "catalog_items_legacy_fixedwidth.txt")
    with open(legacy_path, "w") as f:
        for bc in barcodes[:600]:
            code = rng.choice(CODES)
            f.write("%-14s%4d%-30s\n" % (bc, code, "Legacy title %s" % bc[-5:]))

    _write_csv(
        os.path.join(out_dir, "acquisitions.csv"),
        [
            {
                "barcode": rng.choice(barcodes),
                "vendor": rng.choice(["Baker", "Ingram", "Midwest"]),
                "cost_usd": "%.2f" % rng.uniform(5, 80),
                "received": _rand_date(rng, "2020-01-01", "2025-06-01"),
            }
            for _ in range(1500)
        ],
        ["barcode", "vendor", "cost_usd", "received"],
    )

    _write_csv(
        os.path.join(out_dir, "returns_audit.tsv"),
        [
            {
                "txn_id": "R%07d" % i,
                "barcode": rng.choice(barcodes),
                "branch_id": rng.choice(BRANCHES),
                "returned_ts": _ts(rng, _rand_date(rng, "2024-07-01", "2025-06-30")),
            }
            for i in range(1, 3001)
        ],
        ["txn_id", "barcode", "branch_id", "returned_ts"],
        delim="\t",
    )

    _write_json(
        os.path.join(out_dir, "ill_requests.json"),
        [
            {
                "ill_id": "ILL%05d" % i,
                "patron_id": rng.choice(patron_ids),
                "lender": rng.choice(["SystemA", "SystemB", "SystemC"]),
                "status": rng.choice(["OPEN", "SHIPPED", "RETURNED"]),
            }
            for i in range(1, 401)
        ],
    )

    _write_csv(
        os.path.join(out_dir, "calendar.csv"),
        [
            {
                "date": datetime.date.fromordinal(o).isoformat(),
                "is_open": (datetime.date.fromordinal(o).weekday() != 6),
            }
            for o in range(
                datetime.date(2024, 1, 1).toordinal(),
                datetime.date(2025, 12, 31).toordinal() + 1,
            )
        ],
        ["date", "is_open"],
    )

    _write_csv(
        os.path.join(out_dir, "staff.csv"),
        [
            {
                "staff_id": "ST%04d" % i,
                "branch_id": rng.choice(BRANCHES),
                "role": rng.choice(["LIBRARIAN", "CLERK", "PAGE", "MANAGER"]),
            }
            for i in range(1, 251)
        ],
        ["staff_id", "branch_id", "role"],
    )

    _write_csv(
        os.path.join(out_dir, "fines_payments.csv"),
        [
            {
                "payment_id": "PM%06d" % i,
                "patron_id": rng.choice(patron_ids),
                "amount_usd": "%.2f" % rng.uniform(0.25, 35.0),
                "method": rng.choice(["CASH", "CARD", "ONLINE"]),
            }
            for i in range(1, 1501)
        ],
        ["payment_id", "patron_id", "amount_usd", "method"],
    )

    _write_csv(
        os.path.join(out_dir, "hold_shelf.csv"),
        [
            {
                "barcode": rng.choice(barcodes),
                "branch_id": rng.choice(BRANCHES),
                "expires": _rand_date(rng, "2025-01-01", "2025-12-31"),
            }
            for _ in range(800)
        ],
        ["barcode", "branch_id", "expires"],
    )

    _write_csv(
        os.path.join(out_dir, "catalog_authors.tsv"),
        [
            {"barcode": bc, "author": "Author %d" % rng.randint(1, 2000)}
            for bc in rng.sample(barcodes, 4000)
        ],
        ["barcode", "author"],
        delim="\t",
    )

    _write_csv(
        os.path.join(out_dir, "catalog_subjects.csv"),
        [
            {
                "barcode": bc,
                "subject": rng.choice(
                    ["HISTORY", "SCIENCE", "ARTS", "COOKING", "TRAVEL"]
                ),
            }
            for bc in rng.sample(barcodes, 4000)
        ],
        ["barcode", "subject"],
    )

    older = _make_events(rng, barcodes, 12000, "2020-01-01", "2021-12-31", "O")
    _write_csv(
        os.path.join(out_dir, "circ_transactions_2022.csv"),
        older,
        LIVE_HEADER,
    )

    _write_json(
        os.path.join(out_dir, "ebook_loans.json"),
        [
            {
                "loan_id": "EB%06d" % i,
                "patron_id": rng.choice(patron_ids),
                "platform": rng.choice(["OverDrive", "Hoopla", "Libby"]),
                "loan_date": _rand_date(rng, "2024-07-01", "2025-06-30"),
            }
            for i in range(1, 2501)
        ],
    )

    _write_csv(
        os.path.join(out_dir, "door_counts.csv"),
        [
            {
                "branch_id": b,
                "date": _rand_date(rng, "2024-07-01", "2025-06-30"),
                "count": rng.randint(50, 1200),
            }
            for b in BRANCHES
            for _ in range(120)
        ],
        ["branch_id", "date", "count"],
    )

    _write_csv(
        os.path.join(out_dir, "room_bookings.csv"),
        [
            {
                "booking_id": "RB%05d" % i,
                "branch_id": rng.choice(BRANCHES),
                "room": rng.choice(["A", "B", "C"]),
                "date": _rand_date(rng, "2024-07-01", "2025-06-30"),
            }
            for i in range(1, 901)
        ],
        ["booking_id", "branch_id", "room", "date"],
    )

    _write_csv(
        os.path.join(out_dir, "events_programs.csv"),
        [
            {
                "program_id": "PG%05d" % i,
                "branch_id": rng.choice(BRANCHES),
                "attendance": rng.randint(0, 150),
                "date": _rand_date(rng, "2024-07-01", "2025-06-30"),
            }
            for i in range(1, 701)
        ],
        ["program_id", "branch_id", "attendance", "date"],
    )

    _write_csv(
        os.path.join(out_dir, "volunteer_hours.csv"),
        [
            {
                "volunteer_id": "VL%04d" % i,
                "branch_id": rng.choice(BRANCHES),
                "hours": rng.randint(1, 40),
            }
            for i in range(1, 401)
        ],
        ["volunteer_id", "branch_id", "hours"],
    )

    _write_csv(
        os.path.join(out_dir, "budget_lines.csv"),
        [
            {
                "line_id": "BL%04d" % i,
                "category": rng.choice(["BOOKS", "MEDIA", "STAFF", "FACILITIES"]),
                "amount_usd": "%.2f" % rng.uniform(1000, 90000),
            }
            for i in range(1, 121)
        ],
        ["line_id", "category", "amount_usd"],
    )

    _write_csv(
        os.path.join(out_dir, "vendor_invoices.csv"),
        [
            {
                "invoice_id": "VI%05d" % i,
                "vendor": rng.choice(["Baker", "Ingram", "Midwest"]),
                "amount_usd": "%.2f" % rng.uniform(100, 9000),
            }
            for i in range(1, 501)
        ],
        ["invoice_id", "vendor", "amount_usd"],
    )

    _write_csv(
        os.path.join(out_dir, "branch_hours.csv"),
        [
            {
                "branch_id": b,
                "weekday": d,
                "open": "09:00",
                "close": rng.choice(["17:00", "20:00", "21:00"]),
            }
            for b in BRANCHES
            for d in range(7)
        ],
        ["branch_id", "weekday", "open", "close"],
    )

    _write_csv(
        os.path.join(out_dir, "patron_types.csv"),
        [
            {"patron_type": t, "description": d, "loan_limit": lim}
            for t, d, lim in [
                ("ADULT", "Adult cardholder", 50),
                ("JUVENILE", "Juvenile cardholder", 30),
                ("SENIOR", "Senior cardholder", 50),
                ("STAFF", "Staff cardholder", 100),
            ]
        ],
        ["patron_type", "description", "loan_limit"],
    )

    _write_csv(
        os.path.join(out_dir, "shelf_locations.csv"),
        [
            {
                "barcode": bc,
                "branch_id": rng.choice(BRANCHES),
                "shelf": "%s-%03d"
                % (rng.choice(["NF", "FIC", "JUV"]), rng.randint(1, 400)),
            }
            for bc in rng.sample(barcodes, 3000)
        ],
        ["barcode", "branch_id", "shelf"],
    )

    _write_csv(
        os.path.join(out_dir, "damaged_items.csv"),
        [
            {
                "barcode": rng.choice(barcodes),
                "branch_id": rng.choice(BRANCHES),
                "reported": _rand_date(rng, "2024-07-01", "2025-06-30"),
            }
            for _ in range(500)
        ],
        ["barcode", "branch_id", "reported"],
    )

    _write_csv(
        os.path.join(out_dir, "self_check_machines.csv"),
        [
            {
                "machine_id": "MC%03d" % i,
                "branch_id": rng.choice(BRANCHES),
                "vendor": rng.choice(["Bibliotheca", "Envisionware"]),
            }
            for i in range(1, 61)
        ],
        ["machine_id", "branch_id", "vendor"],
    )

    _write_json(
        os.path.join(out_dir, "wifi_sessions.json"),
        [
            {
                "branch_id": rng.choice(BRANCHES),
                "date": _rand_date(rng, "2024-07-01", "2025-06-30"),
                "sessions": rng.randint(10, 900),
            }
            for _ in range(600)
        ],
    )


if __name__ == "__main__":
    generate(int(sys.argv[1]), sys.argv[2])
    print("wrote lake to", sys.argv[2])
