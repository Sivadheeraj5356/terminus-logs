#!/usr/bin/env python3
"""Regenerate the disk-image valid corpus and the held-out exploit corpus.

The byte layout produced here mirrors the compiled disk image the C reader under
environment/src parses: an 8-byte superblock (a 4-byte magic "DFIM", a version
byte, a region count), a region table of nine-byte entries (kind, offset, size),
and then the names, volumes, inodes, links, and xattrs regions in some order. All
multi-byte integers are big-endian. An inode's uid is a fixed-width unsigned
32-bit value; counts, indices, modification-time deltas, flags, and lengths are
LEB128 varints. Valid files land in environment/testdata/valid; exploit files
land in tests/exploits. Each exploit drives one latent memory-safety weakness in
the unhardened binary and is rejected cleanly by the hardened binary.
"""

import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VALID = ROOT / "environment" / "testdata" / "valid"
EXPLOITS = ROOT / "tests" / "exploits"

MAGIC = b"DFIM"
VERSION = 2
SUPER_SIZE = 8
REGENT = 9  # kind byte + u32 offset + u32 size

REG_NAMES, REG_VOLUMES, REG_INODES, REG_LINKS, REG_XATTRS = 0, 1, 2, 3, 4
DEFAULT_ORDER = (REG_NAMES, REG_VOLUMES, REG_INODES, REG_LINKS, REG_XATTRS)

KIND_FILE, KIND_DIR = 0, 1


def u32(v):
    return struct.pack(">I", v & 0xFFFFFFFF)


def uleb(v):
    out = bytearray()
    while True:
        byte = v & 0x7F
        v >>= 7
        if v:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            break
    return bytes(out)


def sleb(v):
    out = bytearray()
    while True:
        byte = v & 0x7F
        v >>= 7  # python arithmetic shift keeps the sign
        last = (v == 0 and not (byte & 0x40)) or (v == -1 and (byte & 0x40))
        if not last:
            byte |= 0x80
        out.append(byte)
        if last:
            break
    return bytes(out)


class Names:
    """Builds a names pool of NUL-terminated strings and hands back offsets."""

    def __init__(self):
        self.blob = bytearray()
        self.offsets = {}

    def add(self, s):
        if s not in self.offsets:
            self.offsets[s] = len(self.blob)
            self.blob += s.encode() + b"\x00"
        return self.offsets[s]


def volume(label_off, base_lba, flags):
    return {"label_off": label_off, "base_lba": base_lba, "flags": flags}


def volumes_section(vlist):
    if not vlist:
        return b""
    out = bytearray(uleb(len(vlist)))
    for v in vlist:
        out += u32(v["label_off"]) + sleb(v["base_lba"]) + uleb(v["flags"])
    return bytes(out)


def i_file(uid, mtime_delta, data):
    return {"kind": KIND_FILE, "uid": uid, "mtime_delta": mtime_delta,
            "data": data}


def i_dir(uid, mtime_delta, children):
    return {"kind": KIND_DIR, "uid": uid, "mtime_delta": mtime_delta,
            "children": children}


def enc_inode(r):
    out = u32(r["uid"]) + sleb(r["mtime_delta"]) + bytes([r["kind"]])
    if r["kind"] == KIND_FILE:
        out += uleb(len(r["data"])) + r["data"]
    else:
        out += uleb(len(r["children"]))
        for f in r["children"]:
            out += uleb(f)
    return out


def inodes_section(ilist):
    out = bytearray(uleb(len(ilist)))
    for r in ilist:
        out += enc_inode(r)
    return bytes(out)


def hardlink(a, b, weight):
    return uleb(a) + uleb(b) + sleb(weight)


def links_section(links):
    if not links:
        return b""
    out = bytearray(uleb(len(links)))
    for a, b, weight in links:
        out += hardlink(a, b, weight)
    return bytes(out)


def xattr(inode_index, key, value):
    return uleb(inode_index) + uleb(key) + uleb(len(value)) + value


def xattrs_section(xattrs):
    if not xattrs:
        return b""
    out = bytearray(uleb(len(xattrs)))
    for ix, key, value in xattrs:
        out += xattr(ix, key, value)
    return bytes(out)


def resolve_bytes(ilist, idx, _memo=None):
    if _memo is None:
        _memo = {}
    if idx in _memo:
        return _memo[idx]
    r = ilist[idx]
    if r["kind"] == KIND_FILE:
        v = len(r["data"])
    else:
        v = sum(resolve_bytes(ilist, f, _memo) for f in r["children"])
    _memo[idx] = v
    return v


def summary(version, vlist, ilist, links, xattrs):
    return {
        "format_version": version,
        "volumes_defined": len(vlist),
        "inodes_defined": len(ilist),
        "file_inodes": sum(1 for r in ilist if r["kind"] == KIND_FILE),
        "dir_inodes": sum(1 for r in ilist if r["kind"] == KIND_DIR),
        "hardlinks_parsed": len(links),
        "xattrs_parsed": len(xattrs),
        "data_bytes": resolve_bytes(ilist, 0) if ilist else 0,
    }


def container(regions, order=DEFAULT_ORDER, overrides=None, count_override=None,
              version=VERSION):
    overrides = overrides or {}
    n_entries = len(order)
    placed = {}
    cursor = SUPER_SIZE + n_entries * REGENT
    for kind in order:
        placed[kind] = (cursor, len(regions[kind]))
        cursor += len(regions[kind])

    reg_count = n_entries if count_override is None else count_override
    out = bytearray()
    out += MAGIC
    out += bytes([version, reg_count & 0xFF, 0, 0])
    for kind in order:
        off, size = overrides.get(kind, placed[kind])
        out += bytes([kind]) + u32(off) + u32(size)
    for kind in order:
        out += regions[kind]
    return bytes(out)


def assemble(names, vlist, ilist, links, xattrs, order=DEFAULT_ORDER,
             overrides=None, count_override=None, version=VERSION):
    regs = {
        REG_NAMES: bytes(names.blob),
        REG_VOLUMES: volumes_section(vlist),
        REG_INODES: inodes_section(ilist),
        REG_LINKS: links_section(links),
        REG_XATTRS: xattrs_section(xattrs),
    }
    return container(regs, order=order, overrides=overrides,
                     count_override=count_override, version=version)


def build_valid():
    files = {}

    # 001: a single volume and a single file inode with three resident bytes.
    nm = Names()
    a = nm.add("root0")
    vl = [volume(a, 0, 65535)]
    il = [i_file(100, 0, b"\x01\x02\x03")]
    files["valid_001.dfi"] = (assemble(nm, vl, il, [], []),
                              summary(VERSION, vl, il, [], []))

    # 002: two file inodes and one hardlink edge between them.
    nm = Names()
    a, b = nm.add("vol0"), nm.add("vol1")
    vl = [volume(a, 1, 256), volume(b, 1, 256)]
    il = [i_file(1, 3, b"\xaa\xbb"), i_file(2, 4, b"\x01\x02\x03")]
    links = [(0, 1, -5)]
    files["valid_002.dfi"] = (assemble(nm, vl, il, links, []),
                              summary(VERSION, vl, il, links, []))

    # 003: a directory root assembled from two file inodes, plus one xattr.
    nm = Names()
    c = nm.add("disk")
    vl = [volume(c, 1, 512)]
    il = [i_dir(0, 0, [1, 2]),
          i_file(1, 1, b"\x00\x01"),
          i_file(2, 1, b"\x00\x01\x02")]
    xattrs = [(0, 100, b"hi")]
    files["valid_003.dfi"] = (assemble(nm, vl, il, [], xattrs),
                              summary(VERSION, vl, il, [], xattrs))

    # 004: boundary, a volume feature-flags word that is a maximal ten-byte
    # ULEB128 value a bound on over-long varints must still accept.
    nm = Names()
    m = nm.add("m")
    vl = [volume(m, 0, 1 << 63)]  # flags encodes to ten ULEB128 bytes
    il = [i_file(6, 0, b"\x07")]
    files["valid_004.dfi"] = (assemble(nm, vl, il, [], []),
                              summary(VERSION, vl, il, [], []))

    # 005: boundary, the inodes region is placed last so its resident run ends
    # exactly at the end of the file with no trailing bytes.
    nm = Names()
    f = nm.add("fit")
    vl = [volume(f, 1, 128)]
    il = [i_file(12, 0, b"\x01\x02\x03\x04")]
    files["valid_005.dfi"] = (
        assemble(nm, vl, il, [], [],
                 order=(REG_NAMES, REG_VOLUMES, REG_LINKS, REG_XATTRS,
                        REG_INODES)),
        summary(VERSION, vl, il, [], []),
    )

    # 006: a directory whose only child is the inode at the very last index,
    # which an off-by-one index bound would wrongly reject.
    nm = Names()
    r = nm.add("r")
    vl = [volume(r, 1, 64)]
    il = [i_dir(0, 0, [2]),
          i_file(1, 0, b"\x00"),
          i_file(2, 0, b"\x00\x01\x02\x03")]
    files["valid_006.dfi"] = (assemble(nm, vl, il, [], []),
                              summary(VERSION, vl, il, [], []))

    # 007: a hardlink edge whose both members are the inode at the last index,
    # which an off-by-one index bound would wrongly reject.
    nm = Names()
    p = nm.add("p")
    vl = [volume(p, 1, 64)]
    il = [i_file(5, 0, b"\x09\x08"), i_file(5, 0, b"\x07")]
    links = [(1, 1, 3)]
    files["valid_007.dfi"] = (assemble(nm, vl, il, links, []),
                              summary(VERSION, vl, il, links, []))

    # 008: boundary, a deep but legal directory chain twenty levels deep; a
    # recursion-depth bound must be set high enough to still resolve it.
    nm = Names()
    depth = 20
    vl = [volume(nm.add("deep"), 1, 64)]
    il = []
    for i in range(depth):
        il.append(i_dir(i, 0, [i + 1]))
    il.append(i_file(depth, 0, b"\x00\x01"))
    files["valid_008.dfi"] = (assemble(nm, vl, il, [], []),
                              summary(VERSION, vl, il, [], []))

    # 009: boundary, the names region placed last so it ends exactly at the end
    # of the file, with the volume's label at the last offset in the pool.
    nm = Names()
    nm.add("first")
    last = nm.add("last")
    vl = [volume(last, 1, 64)]
    il = [i_file(5, 0, b"\x02\x03")]
    files["valid_009.dfi"] = (
        assemble(nm, vl, il, [], [],
                 order=(REG_VOLUMES, REG_INODES, REG_LINKS, REG_XATTRS,
                        REG_NAMES)),
        summary(VERSION, vl, il, [], []),
    )

    # 010: negative mtime deltas and hardlink weight (signed LEB128), plus an
    # xattr with a multi-byte value placed last so the value ends at end of file.
    nm = Names()
    vl = [volume(nm.add("neg"), -2, 64)]
    il = [i_file(1, -12345, b"\x01\x02"), i_file(2, -1, b"\x03")]
    links = [(0, 1, -7)]
    xattrs = [(1, 30, b"label")]
    files["valid_010.dfi"] = (
        assemble(nm, vl, il, links, xattrs,
                 order=(REG_NAMES, REG_VOLUMES, REG_INODES, REG_LINKS,
                        REG_XATTRS)),
        summary(VERSION, vl, il, links, xattrs),
    )

    # 011: a directory image with shared-subtree multiplicity. Each directory
    # lists the next one twice, so the footprint doubles at every level and the
    # total (4096) is far larger than the handful of inodes. It is well-formed
    # and must be totalled exactly, which a resolver that re-walks each shared
    # subtree every time it is named cannot do in bounded time once the sharing
    # is wide.
    nm = Names()
    vl = [volume(nm.add("share"), 1, 64)]
    depth = 12
    il = []
    for i in range(depth):
        il.append(i_dir(i, 0, [i + 1, i + 1]))
    il.append(i_file(depth, 0, b"\x00"))
    files["valid_011.dfi"] = (assemble(nm, vl, il, [], []),
                              summary(VERSION, vl, il, [], []))

    return files


def one_volume(nm=None):
    """A minimal names pool and a single label, for exploits that need a valid
    label present before the weakness is reached."""
    if nm is None:
        nm = Names()
    nm.add("a")
    return nm


def build_exploits():
    files = {}

    # super: a region count far larger than the table that follows drives the
    # table walk off the end of the file.
    nm = one_volume()
    il = [i_file(0, 0, b"")]
    files["exploit_super.dfi"] = assemble(nm, [], il, [], [], count_override=0xFF)

    # regtab: the inodes region is declared far outside the file, so reading it
    # lands out of bounds.
    nm = one_volume()
    il = [i_file(0, 0, b"")]
    files["exploit_regtab.dfi"] = assemble(
        nm, [], il, [], [], overrides={REG_INODES: (0x40000000, 8)})

    # uleb: an inode count made of continuation bytes runs off the end of the
    # inodes region, which sits at the end of the file.
    nm = one_volume()
    regs = {
        REG_NAMES: bytes(nm.blob),
        REG_VOLUMES: b"",
        REG_LINKS: b"",
        REG_XATTRS: b"",
        REG_INODES: b"\x80" * 6,
    }
    files["exploit_uleb.dfi"] = container(
        regs, order=(REG_NAMES, REG_VOLUMES, REG_LINKS, REG_XATTRS,
                     REG_INODES))

    # sleb: an inode mtime delta made of continuation bytes runs off the end of
    # the inodes region, which sits at the end of the file.
    nm = one_volume()
    bad = uleb(1) + u32(0) + b"\x80" * 6
    regs = {
        REG_NAMES: bytes(nm.blob),
        REG_VOLUMES: b"",
        REG_LINKS: b"",
        REG_XATTRS: b"",
        REG_INODES: bad,
    }
    files["exploit_sleb.dfi"] = container(
        regs, order=(REG_NAMES, REG_VOLUMES, REG_LINKS, REG_XATTRS,
                     REG_INODES))

    # inode (alloc): an inode count whose byte size overflows a 32-bit multiply
    # under-allocates the inode array the walk then overruns.
    nm = one_volume()
    body = uleb(0x20000000) + u32(0) + sleb(0) + bytes([KIND_FILE]) + uleb(0)
    regs = {
        REG_NAMES: bytes(nm.blob),
        REG_VOLUMES: b"",
        REG_INODES: body,
        REG_LINKS: b"",
        REG_XATTRS: b"",
    }
    files["exploit_alloc.dfi"] = container(regs)

    # inode (walk): an inode count of two with only one entry present runs the
    # second entry's field reads off the end of the inodes region at EOF.
    nm = one_volume()
    body = uleb(2) + (u32(0) + sleb(0) + bytes([KIND_FILE]) + uleb(0))
    regs = {
        REG_NAMES: bytes(nm.blob),
        REG_VOLUMES: b"",
        REG_LINKS: b"",
        REG_XATTRS: b"",
        REG_INODES: body,
    }
    files["exploit_iwalk.dfi"] = container(
        regs, order=(REG_NAMES, REG_VOLUMES, REG_LINKS, REG_XATTRS,
                     REG_INODES))

    # name: a volume label offset points far past the end of the names pool.
    nm = one_volume()
    vl = [volume(0x40000000, 1, 64)]
    il = [i_file(0, 0, b"")]
    files["exploit_name.dfi"] = assemble(nm, vl, il, [], [])

    # data: a file inode claims far more resident bytes than its region holds, so
    # the resident run reads off the end of the inodes region at EOF.
    nm = one_volume()
    body = uleb(1) + u32(0) + sleb(0) + bytes([KIND_FILE]) + uleb(1000) + b"\x01\x02"
    regs = {
        REG_NAMES: bytes(nm.blob),
        REG_VOLUMES: b"",
        REG_LINKS: b"",
        REG_XATTRS: b"",
        REG_INODES: body,
    }
    files["exploit_data.dfi"] = container(
        regs, order=(REG_NAMES, REG_VOLUMES, REG_LINKS, REG_XATTRS,
                     REG_INODES))

    # child: a directory child index points far past the end of the inode array,
    # so resolving the root reads out of bounds.
    nm = one_volume()
    il = [i_dir(0, 0, [0x40000000])]
    files["exploit_child.dfi"] = assemble(nm, [], il, [], [])

    # child (deep): a directory chain far deeper than any real image, so the
    # recursive resolve runs the stack off its end unless depth is bounded.
    nm = Names()
    n = 200000
    il = []
    for i in range(n):
        il.append(i_dir(i, 0, [i + 1]))
    il.append(i_file(n, 0, b"\x00"))
    files["exploit_deep.dfi"] = assemble(nm, [], il, [], [])

    # child (cycle): a directory that lists itself as a child, so the recursive
    # resolve never terminates unless depth is bounded.
    nm = one_volume()
    il = [i_dir(0, 0, [0])]
    files["exploit_cycle.dfi"] = assemble(nm, [], il, [], [])

    # link (walk): a hardlink count of two with only one edge present runs the
    # second edge's reads off the end of the links region at EOF.
    nm = one_volume()
    il = [i_file(0, 0, b"")]
    regs = {
        REG_NAMES: bytes(nm.blob),
        REG_VOLUMES: b"",
        REG_INODES: inodes_section(il),
        REG_XATTRS: b"",
        REG_LINKS: uleb(2) + hardlink(0, 0, 0),
    }
    files["exploit_linkwalk.dfi"] = container(
        regs, order=(REG_NAMES, REG_VOLUMES, REG_INODES, REG_XATTRS,
                     REG_LINKS))

    # link (index): a hardlink edge inode index points far past the end of the
    # inode array, so looking the edge up reads out of bounds.
    nm = one_volume()
    il = [i_file(0, 0, b"")]
    links = [(0x40000000, 0, 0)]
    files["exploit_linkidx.dfi"] = assemble(nm, [], il, links, [])

    # xattr: an xattr value length runs far past the xattrs region, so scanning
    # the value reads off the end of the file.
    nm = one_volume()
    il = [i_file(0, 0, b"")]
    regs = {
        REG_NAMES: bytes(nm.blob),
        REG_VOLUMES: b"",
        REG_INODES: inodes_section(il),
        REG_LINKS: b"",
        REG_XATTRS: uleb(1) + uleb(0) + uleb(0) + uleb(0x10000000),
    }
    files["exploit_xattr.dfi"] = container(
        regs, order=(REG_NAMES, REG_VOLUMES, REG_INODES, REG_LINKS,
                     REG_XATTRS))

    # vol (field): a volume count of one with no descriptor present runs the
    # fixed-width label-offset read off the end of the volumes region at EOF.
    nm = one_volume()
    il = [i_file(0, 0, b"")]
    regs = {
        REG_NAMES: bytes(nm.blob),
        REG_INODES: inodes_section(il),
        REG_LINKS: b"",
        REG_XATTRS: b"",
        REG_VOLUMES: uleb(1),
    }
    files["exploit_volfield.dfi"] = container(
        regs, order=(REG_NAMES, REG_INODES, REG_LINKS, REG_XATTRS,
                     REG_VOLUMES))

    return files


def main():
    VALID.mkdir(parents=True, exist_ok=True)
    EXPLOITS.mkdir(parents=True, exist_ok=True)

    valid = build_valid()
    summaries = {}
    for name, (data, summ) in valid.items():
        (VALID / name).write_bytes(data)
        summaries[name] = summ

    exploits = build_exploits()
    for name, data in exploits.items():
        (EXPLOITS / name).write_bytes(data)

    print(json.dumps(summaries, indent=2))
    print("exploits:", sorted(exploits))
    return 0


if __name__ == "__main__":
    sys.exit(main())
