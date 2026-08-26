# Data dictionary

Reference for the files in this lake: what each one records and its columns.
Several files describe overlapping activity. This dictionary documents what each
file contains; it does not say which file to use for any particular question.

## Circulation

`circ_transactions_<YYYY>.csv`
  Per-event circulation log, one file per calendar year, named for the calendar
  year of the events it holds. One row per exported event.

    txn_id        Event identifier (text).
    barcode       Item barcode, 14-character zero-padded (text).
    branch_id     Branch where the event occurred (text).
    txn_type      One of CHECKOUT, RENEW, RETURN, HOLD_FILLED.
    txn_ts        Event timestamp, ISO 8601 in UTC with a trailing Z.
    status        OK or VOID. VOID marks a transaction that was reversed.
    ingest_batch  Integer id of the synchronization batch that produced the row.
                  The log is rebuilt from successive batches, and a given event
                  may be carried by more than one batch.

`circ_monthly_rollup.csv`
  Pre-aggregated monthly circulation counts, with no item-level detail.

    month            Calendar month, YYYY-MM.
    branch_id        Branch.
    checkouts_total  Aggregated count with several event types combined.

`circ_sample_vendor.csv`
  A sample of circulation events prepared for a vendor evaluation. Same shape as
  the per-event log minus the ingest_batch column; the barcodes are placeholder
  values.

    txn_id, barcode, branch_id, txn_type, txn_ts, status

`circ_transactions_migrated.txt`
  Per-event circulation exported by the replacement integrated library system the
  consortium cut over to partway through the year. It records the same kind of
  events as the calendar-year log, for the period the new system has owned, and
  those events are not also present in the calendar-year slices. It is a
  fixed-width text file with no header and no delimiter: each field occupies a
  fixed range of character columns (1-indexed, inclusive) and text fields are left
  padded out with spaces.

    txn_id        columns  1-10
    barcode       columns 11-24  (14-character zero-padded, read as text)
    branch_id     columns 25-28
    txn_type      columns 29-40
    txn_ts        columns 41-60  (ISO 8601 UTC with a trailing Z)
    status        columns 61-64
    ingest_batch  columns 65-67

## Catalog

`catalog_items.tsv`
  Item catalog, a periodic re-export of the cataloging system. A re-export can
  carry more than one row for an item as its record is revised over time.

    barcode         14-character zero-padded barcode (text).
    item_type_code  Integer item-type code (see item_type_codes.csv).
    title           Item title.
    acquired_date   Date the item was acquired (YYYY-MM-DD).
    record_updated  Date this record was last updated (YYYY-MM-DD).

`item_type_codes.csv`
  Maps each item-type code to its collection.

    item_type_code  Integer code.
    collection      One of ADULT_NONFICTION, ADULT_FICTION, JUVENILE,
                    PERIODICAL, MEDIA.
    description     Human-readable label.

`catalog_authors.tsv`, `catalog_subjects.csv`
  Author and subject side tables, each keyed by barcode.

## Branches

`branches.csv`
    branch_id, branch_name, region   Current branches.

`branch_consolidations.csv`
  Outlet mergers.

    retired_branch_id    A branch id that was retired.
    surviving_branch_id  The branch it was merged into.
    merged_on            Date of the merger (YYYY-MM-DD).

## Other exports

The lake also holds operational exports that are not circulation: patrons and
patron types, holds and the hold shelf, fines and payments, interlibrary loan
and ebook/digital loans, door counts, wifi sessions, room bookings, events and
programs, acquisitions, vendor invoices, budget lines, staff, volunteer hours,
damaged items, self-check machines, shelf locations, the calendar, branch hours,
and a returns audit. Each file's columns are in its header.
