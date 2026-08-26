# Quarantine extraction security contract

This document is authoritative for `/app`. A submission is either published in
full or rejected in full.

## Interface and publication

The binary accepts exactly two positional arguments:

```text
quarantine-extractor <archive> <destination>
```

Both paths must be absolute. The archive must be a regular file reached without
following a symbolic link. The destination must not already exist, and its
parent must be an existing real directory reached without symbolic links.
In Rust, `fs::canonicalize` follows symlinks, so it is not sufficient evidence
that a path was reached without symlinks. Check `fs::symlink_metadata` and
reject `file_type().is_symlink()` before any canonicalization or path
resolution.

Success returns status `0` and atomically renames a private staging directory
beside the destination into place. Rejection returns a nonzero status. On
rejection the destination remains absent, bytes outside it are unchanged, and
no staging directory remains. Never extract directly into the final path.

## Supported archives and recursive layout

Root and nested formats are identified by bytes, never by a filename suffix:

- ZIP uses a standard `PK` local-file, empty-archive, or spanned signature.
- TAR uses a checksum-valid POSIX `ustar` header.

Names and link payloads must be valid UTF-8. Unsupported, truncated, encrypted,
or malformed structures are rejected. A regular entry whose bytes identify a
supported archive is recursively expanded. Its entry path becomes a directory
containing that archive's entries; the carrier bytes are not also published.
For example, `evidence.bin` containing ZIP bytes becomes the directory
`evidence.bin/`. A file such as `looks.zip` whose bytes are not archive bytes
remains an ordinary file.

The root archive is depth zero. At most 3 nested archive boundaries beneath the
root are allowed.

## Archive parser agreement

The quarantine decision must not depend on which redundant archive index a
parser trusts. For each single-disk, non-ZIP64 ZIP, every central-directory
record must identify exactly one local file record and every local file record
must be listed. The local and central records must agree on their raw name
bytes, general-purpose flags, compression method, CRC, compressed size, and
decoded size. When the data-descriptor flag is set, zero local CRC and size
fields are allowed, but the descriptor after the compressed payload must agree
with the central record. Reject encrypted records, duplicate or overlapping
local offsets, unlisted local records, unexplained bytes between local records,
and bytes between the final local record and the central directory. Thus a
local name such as `../escape.txt` paired with central name `safe-file.txt`, or
an unlisted `orphan.bin` local record before `reviewed.txt`, is a parser
differential and must be rejected.

A TAR ends at two consecutive 512-byte zero blocks. Every byte after those
blocks must also be zero padding. Reject a concatenated TAR or any nonzero
payload hidden after the end marker, even when a high-level iterator exposes
only the entries before the marker.

## Portable path identity

Archive entry names are relative slash-separated paths. Reject an empty name,
an absolute or UNC name, a Windows drive prefix, a backslash, NUL or control
character, an empty component, and any `.` or `..` component. A trailing slash
is allowed only for a directory declaration.

Each component is limited to 64 UTF-8 bytes. The complete relative path is
limited to 240 UTF-8 bytes and 16 components.

For collision checks, normalize every component with Unicode NFKC and then
apply Unicode lowercase mapping. This collision key is used across every
archive layer, including implicit parent directories. Reject duplicate files,
file/directory prefix conflicts, and distinct spellings with the same key.
Exact same-spelling duplicates are duplicates too: a ZIP containing two
separate `duplicate.txt` records must be rejected even if a ZIP library's
by-name lookup would silently collapse the central-directory entries. Thus
composed and decomposed `café`, `Admin` and `admin`, exact duplicates such as
`duplicate.txt` and `duplicate.txt`, and compatibility forms such as `Key` and
`key` collide. A single safe name such as `Résumé.txt` does not collide with
itself.

## Entry types and links

Accept regular files and directories. Preserve only the executable bit class:
regular files are published as mode `0644`, or `0755` when any archived execute
bit is set. Directories use mode `0755`. Ignore ownership, timestamps, and all
set-id or sticky bits.

TAR symbolic links and hard links are accepted only when their final target is
a regular file supplied by the same archive namespace:

- a symbolic-link target is interpreted relative to the link's parent;
- a TAR hard-link target is interpreted relative to the root of its current
  archive layer;
- targets must be relative UTF-8 slash paths. `.` and `..` may occur only when
  lexical resolution stays inside the current archive layer;
- the target spelling and portable collision identity must match the supplied
  regular file exactly. Link chains, dangling links, and links to directories
  or nested-archive directories are rejected;
- accepted TAR hard links must be materialized as filesystem hard links to the
  supplied regular file, not as independent file copies.

For example, `docs/latest.txt` may safely point to `report.txt`, and
`copies/report.txt` may hard-link to `docs/report.txt`. ZIP Unix symbolic links
use mode `0120777` and store the target text as their payload. Other ZIP Unix
special modes are rejected.

Reject TAR character devices, block devices, FIFOs, sockets, GNU sparse type
records, and all sparse declarations carried in PAX metadata. No special node
may be materialized.
High-level TAR APIs can hide PAX sparse declarations by applying extension
headers before exposing the following regular file. Inspect raw TAR bytes for
PAX extension blocks containing `GNU.sparse.*` keys before passing the archive
to a high-level iterator.

## Resource limits

All limits apply before publication and across the complete recursive
submission:

- at most 64 archive entries, including directories and links;
- at most 262144 decoded bytes in one regular entry, including a nested archive
  carrier;
- at most 1048576 decoded regular-entry bytes in aggregate. Carrier bytes count
  even when they are recursively expanded, as do the nested decoded entries;
- at most 2097152 bytes in the root archive and in any archive carrier;
- for every nonempty ZIP file entry, decoded size must be at most 32 times its
  compressed size. A nonempty entry with zero compressed bytes is rejected.

Declared sizes are untrusted and must be checked before allocation or copying,
then checked against the actual decoded byte count. Entry counts, decoded-byte
budgets, compression ratios, recursive depth, sparse logical sizes, and all
integer arithmetic fail closed on overflow or disagreement.

## Documented safe archive examples

A safe TAR may contain `docs/report.txt` with the bytes `incident report`,
`docs/latest.txt` pointing to `report.txt`, and `copies/report.txt` hard-linked
to `docs/report.txt`. A safe nested ZIP may contain
`nested/receipt.txt` with the bytes `quarantine receipt`. A safe plain file
named `looks.zip` may contain `not an archive`.

A safe ZIP may contain `records/primary.txt` with the bytes `primary record`,
`records/run-verify.sh` as an executable file, `records/alias.txt` pointing to
`primary.txt`, and a content-identified nested TAR at `nested/payload.dat`
containing `chain.txt` with the bytes `nested chain`.
A safe ZIP may also carry `descriptor.txt` with the bytes `descriptor payload`
using a standard data descriptor whose CRC and sizes agree with the central
directory.
