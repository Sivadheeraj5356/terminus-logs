"""Canonical TZif version 2 serialisation (RFC 8536) as pinned by TZIF-CANONICAL.md."""

import hashlib
import struct

from .timeline import INT32_MAX, INT32_MIN

MAGIC = b"TZif"


def _designations(types):
    buf = bytearray()
    offs = []
    for _, _, abbrev, _, _ in types:
        offs.append(len(buf))
        buf.extend(abbrev.encode("ascii"))
        buf.append(0)
    return bytes(buf), offs


def _header(timecnt, typecnt, charcnt):
    return (MAGIC + b"2" + b"\x00" * 15
            + struct.pack(">6I", typecnt, typecnt, 0, timecnt, typecnt, charcnt))


def _block(transitions, types, index, chars, offs, width):
    out = bytearray()
    pack = ">q" if width == 8 else ">i"
    for tr in transitions:
        out.extend(struct.pack(pack, tr.ut))
    for tr in transitions:
        out.append(index[tr.key()])
    for i, (utoff, isdst, _, _, _) in enumerate(types):
        out.extend(struct.pack(">i", utoff))
        out.append(isdst)
        out.append(offs[i])
    out.extend(chars)
    for _, _, _, isstd, _ in types:
        out.append(isstd)
    for _, _, _, _, isut in types:
        out.append(isut)
    return bytes(out)


def serialize(tl):
    types = tl.types
    index = tl.type_index
    chars, offs = _designations(types)
    typecnt, charcnt = len(types), len(chars)

    v1 = [t for t in tl.transitions if INT32_MIN <= t.ut <= INT32_MAX]
    out = bytearray()
    out.extend(_header(len(v1), typecnt, charcnt))
    out.extend(_block(v1, types, index, chars, offs, 4))
    out.extend(_header(len(tl.transitions), typecnt, charcnt))
    out.extend(_block(tl.transitions, types, index, chars, offs, 8))
    out.extend(b"\n" + tl.footer.encode("ascii") + b"\n")
    return bytes(out)


def sha256(data):
    return hashlib.sha256(data).hexdigest()
