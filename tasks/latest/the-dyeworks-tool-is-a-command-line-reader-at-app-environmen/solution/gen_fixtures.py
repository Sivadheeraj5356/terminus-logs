#!/usr/bin/env python3
"""Regenerate the dyeworksmini valid corpus and the held-out exploit corpus.

The byte layout produced here mirrors the compiled dyeworks-tree container the C
reader under environment/src parses: an 8-byte header (a 4-byte magic, a version
byte, a section count), a 4-entry section table, and then the dyeworksdefs, nodes,
lots, and strings sections in some order. All multi-byte integers are
big-endian. Valid files land in environment/testdata/valid; exploit files land
in tests/exploits. Each exploit drives one planted memory-safety bug on the
unpatched binary and is rejected cleanly by the patched binary.
"""

import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VALID = ROOT / "environment" / "testdata" / "valid"
EXPLOITS = ROOT / "tests" / "exploits"

MAGIC = b"DYEW"
HEADER_SIZE = 8
SECENT = 9
SEC_DYEWORKSDEFS, SEC_NODES, SEC_LOTS, SEC_STR = 0, 1, 2, 3

# Spell types used by the corpus.
TYPE_city = 0x01
TYPE_rail = 0x02
TYPE_dyeworks = 0x03
TYPE_car = 0x04
TYPE_booth = 0x05
TYPE_map = 0x06

# Key ids (opaque to the reader; only the form drives byte consumption).
KEY_name = 0x01
KEY_label = 0x02
KEY_index = 0x03
KEY_weight = 0x04
KEY_value = 0x05
KEY_enabled = 0x06
KEY_data = 0x07
KEY_lot = 0x08

FORM_data1 = 0x01
FORM_data2 = 0x02
FORM_data4 = 0x03
FORM_data8 = 0x04
FORM_uleb = 0x05
FORM_sleb = 0x06
FORM_str = 0x07
FORM_string = 0x08
FORM_block1 = 0x09
FORM_block2 = 0x0A
FORM_block4 = 0x0B
FORM_flag = 0x0C
FORM_indirect = 0x10
FORM_lot = 0x11


def u16(v):
    return struct.pack(">H", v & 0xFFFF)


def u32(v):
    return struct.pack(">I", v & 0xFFFFFFFF)


def u64(v):
    return struct.pack(">Q", v & 0xFFFFFFFFFFFFFFFF)


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


class StrTable:
    """Builds a strings blob and hands back offsets."""

    def __init__(self):
        self.blob = bytearray()
        self.offsets = {}

    def add(self, s):
        if s not in self.offsets:
            self.offsets[s] = len(self.blob)
            self.blob += s.encode() + b"\x00"
        return self.offsets[s]


class RuneTable:
    """Builds a lots blob (an array of 4-byte ids) and hands back indices."""

    def __init__(self):
        self.ids = []

    def add(self, lot_id):
        self.ids.append(lot_id)
        return len(self.ids) - 1

    def blob(self):
        out = bytearray()
        for rid in self.ids:
            out += u32(rid)
        return bytes(out)


def dyeworksdef(code, type_, has_children, pairs):
    out = uleb(code) + uleb(type_) + bytes([has_children])
    for key, form in pairs:
        out += uleb(key) + uleb(form)
    out += uleb(0) + uleb(0)
    return out


def dyeworksdef_section(defs):
    return b"".join(defs) + uleb(0)


def encode_form(form, value, strtab, lottab):
    if form == FORM_data1:
        return bytes([value & 0xFF])
    if form == FORM_data2:
        return u16(value)
    if form == FORM_data4:
        return u32(value)
    if form == FORM_data8:
        return u64(value)
    if form == FORM_uleb:
        return uleb(value)
    if form == FORM_sleb:
        return sleb(value)
    if form == FORM_str:
        return u32(strtab.add(value))
    if form == FORM_string:
        return value.encode() + b"\x00"
    if form == FORM_block1:
        return bytes([len(value)]) + value
    if form == FORM_block2:
        return u16(len(value)) + value
    if form == FORM_block4:
        return u32(len(value)) + value
    if form == FORM_flag:
        return b""
    if form == FORM_lot:
        return u32(lottab.add(value))
    if form == FORM_indirect:
        real_form, real_value = value
        return uleb(real_form) + encode_form(real_form, real_value, strtab, lottab)
    raise ValueError(f"unhandled form 0x{form:x}")


def node(code, pairs, values, strtab, lottab, children=None, has_children=False):
    """Serialize one node and, when the declaration carries children, its child
    sibling chain followed by a null node."""
    out = uleb(code)
    for (key, form), v in zip(pairs, values):
        out += encode_form(form, v, strtab, lottab)
    if has_children:
        for ch in children or []:
            out += ch
        out += uleb(0)  # null node ends the child sibling chain
    return out


def nodes_section(
    version,
    dyeworksdef_offset,
    reserved,
    node_count,
    node_bytes,
    unit_length_override=None,
    node_count_override=None,
):
    nc = node_count if node_count_override is None else node_count_override
    body = (
        u16(version) + u32(dyeworksdef_offset) + bytes([reserved]) + u32(nc) + node_bytes
    )
    unit_length = len(body) if unit_length_override is None else unit_length_override
    return u32(unit_length) + body


def container(
    sections,
    version=1,
    order=(SEC_DYEWORKSDEFS, SEC_NODES, SEC_LOTS, SEC_STR),
    overrides=None,
):
    """Lay out the four section blobs in *order* after the table and build the
    table. *overrides* maps a section name to a (offset, size) pair written into
    the table in place of the section's real placement."""
    overrides = overrides or {}
    placed = {}
    cursor = HEADER_SIZE + len(sections) * SECENT
    for name in order:
        placed[name] = (cursor, len(sections[name]))
        cursor += len(sections[name])

    out = bytearray()
    out += MAGIC
    out += bytes([version, len(sections), 0, 0])
    for name in (SEC_DYEWORKSDEFS, SEC_NODES, SEC_LOTS, SEC_STR):
        off, size = overrides.get(name, placed[name])
        out += bytes([name]) + u32(off) + u32(size)
    for name in order:
        out += sections[name]

    return bytes(out)


def summary(version, dyeworksdefs_defined, nodes_parsed, lots_resolved, indirects, root):
    return {
        "version": version,
        "dyeworksdefs_defined": dyeworksdefs_defined,
        "nodes_parsed": nodes_parsed,
        "lots_resolved": lots_resolved,
        "indirects_resolved": indirects,
        "root_type": root,
    }


def assemble(defs, node_bytes, node_count, strtab, lottab, version=4, order=None):
    kw = {} if order is None else {"order": order}
    secs = {
        SEC_DYEWORKSDEFS: dyeworksdef_section(defs),
        SEC_NODES: nodes_section(version, 0, 8, node_count, node_bytes),
        SEC_LOTS: lottab.blob(),
        SEC_STR: bytes(strtab.blob),
    }
    return container(secs, **kw)


# ---------------------------------------------------------------------------
# Valid corpus.
# ---------------------------------------------------------------------------
def build_valid():
    files = {}

    # 001: one declaration, one root range node (name str + label string).
    st, rt = StrTable(), RuneTable()
    w = [(KEY_name, FORM_str), (KEY_label, FORM_string)]
    defs = [dyeworksdef(1, TYPE_city, 0, w)]
    nodes = node(1, w, ["fire.dye", "Fire School"], st, rt)
    files["valid_001.dye"] = (
        assemble(defs, nodes, 1, st, rt, version=4),
        summary(4, 1, 1, 0, 0, "range"),
    )

    # 002: two declarations, root range + a leaf skein child.
    st, rt = StrTable(), RuneTable()
    w = [(KEY_name, FORM_str)]
    e = [(KEY_name, FORM_str), (KEY_index, FORM_data4)]
    defs = [
        dyeworksdef(1, TYPE_city, 1, w),
        dyeworksdef(2, TYPE_car, 0, e),
    ]
    skein = node(2, e, ["burn", 0x00000040], st, rt)
    root = node(1, w, ["arcane"], st, rt, children=[skein], has_children=True)
    files["valid_002.dye"] = (
        assemble(defs, root, 2, st, rt, version=4),
        summary(4, 2, 2, 0, 0, "range"),
    )

    # 003: three declarations, with a mordant carrying an inline string + uleb.
    st, rt = StrTable(), RuneTable()
    w = [(KEY_name, FORM_str)]
    e = [(KEY_name, FORM_str), (KEY_index, FORM_data4)]
    mordant = [(KEY_label, FORM_string), (KEY_value, FORM_uleb)]
    defs = [
        dyeworksdef(1, TYPE_city, 1, w),
        dyeworksdef(2, TYPE_car, 0, e),
        dyeworksdef(3, TYPE_booth, 0, mordant),
    ]
    ef = node(2, e, ["chill", 0x00000080], st, rt)
    co = node(3, mordant, ["weight", 300000], st, rt)
    root = node(1, w, ["frost"], st, rt, children=[ef, co], has_children=True)
    files["valid_003.dye"] = (
        assemble(defs, root, 3, st, rt, version=5),
        summary(5, 3, 3, 0, 0, "range"),
    )

    # 004: a swatch using data1 and a block1 value.
    st, rt = StrTable(), RuneTable()
    w = [(KEY_name, FORM_str)]
    req = [(KEY_weight, FORM_data1), (KEY_data, FORM_block1)]
    defs = [
        dyeworksdef(1, TYPE_city, 1, w),
        dyeworksdef(4, TYPE_map, 0, req),
    ]
    rq = node(4, req, [4, b"\xde\xad\xbe\xef"], st, rt)
    root = node(1, w, ["blob"], st, rt, children=[rq], has_children=True)
    files["valid_004.dye"] = (
        assemble(defs, root, 2, st, rt, version=4),
        summary(4, 2, 2, 0, 0, "range"),
    )

    # 005: a nested child tree closed by null nodes at each level
    # (range > vat > skein).
    st, rt = StrTable(), RuneTable()
    w = [(KEY_name, FORM_str)]
    vat = [(KEY_name, FORM_str), (KEY_index, FORM_data4)]
    eff = [(KEY_label, FORM_string), (KEY_value, FORM_uleb)]
    defs = [
        dyeworksdef(1, TYPE_city, 1, w),
        dyeworksdef(2, TYPE_rail, 1, vat),
        dyeworksdef(3, TYPE_car, 0, eff),
    ]
    ef = node(3, eff, ["local", 7], st, rt)
    ti = node(2, vat, ["novice", 0x00000010], st, rt, children=[ef], has_children=True)
    root = node(1, w, ["root"], st, rt, children=[ti], has_children=True)
    files["valid_005.dye"] = (
        assemble(defs, root, 3, st, rt, version=4),
        summary(4, 3, 3, 0, 0, "range"),
    )

    # 006: boundary, strings placed last so it ends exactly at end of file, and
    # the root's name str points at the very last string in the table.
    st, rt = StrTable(), RuneTable()
    st.add("first")
    w = [(KEY_name, FORM_str)]
    defs = [dyeworksdef(1, TYPE_city, 0, w)]
    nodes = node(1, w, ["last-string-at-eof"], st, rt)
    files["valid_006.dye"] = (
        assemble(
            defs,
            nodes,
            1,
            st,
            rt,
            version=4,
            order=(SEC_DYEWORKSDEFS, SEC_NODES, SEC_LOTS, SEC_STR),
        ),
        summary(4, 1, 1, 0, 0, "range"),
    )

    # 007: boundary, a maximal ten-byte ULEB128 value that a bound on over-long
    # varints must still accept.
    st, rt = StrTable(), RuneTable()
    mordant = [(KEY_label, FORM_string), (KEY_value, FORM_uleb)]
    defs = [dyeworksdef(1, TYPE_city, 0, mordant)]
    big = 1 << 63  # encodes to ten ULEB128 bytes
    nodes = node(1, mordant, ["wide", big], st, rt)
    files["valid_007.dye"] = (
        assemble(defs, nodes, 1, st, rt, version=4),
        summary(4, 1, 1, 0, 0, "range"),
    )

    # 008: boundary, the nodes section placed last so the unit ends exactly at
    # the end of the file with an exact unit length.
    st, rt = StrTable(), RuneTable()
    w = [(KEY_name, FORM_str)]
    e = [(KEY_name, FORM_str), (KEY_index, FORM_data4)]
    defs = [
        dyeworksdef(1, TYPE_city, 1, w),
        dyeworksdef(2, TYPE_car, 0, e),
    ]
    ef = node(2, e, ["run", 0x00000100], st, rt)
    root = node(1, w, ["edge"], st, rt, children=[ef], has_children=True)
    secs = {
        SEC_DYEWORKSDEFS: dyeworksdef_section(defs),
        SEC_NODES: nodes_section(4, 0, 8, 2, root),
        SEC_LOTS: rt.blob(),
        SEC_STR: bytes(st.blob),
    }
    files["valid_008.dye"] = (
        container(secs, order=(SEC_DYEWORKSDEFS, SEC_LOTS, SEC_STR, SEC_NODES)),
        summary(4, 2, 2, 0, 0, "range"),
    )

    # 009: extended forms in a valid unit: a name reached through an indirect
    # form that resolves to str, an eight-byte data value, a two-byte-counted
    # block, a presence flag, a lot reference into the lots table, and a
    # signed varint value.
    st, rt = StrTable(), RuneTable()
    w = [(KEY_name, FORM_str)]
    dyeworks = [
        (KEY_name, FORM_indirect),
        (KEY_weight, FORM_data8),
        (KEY_data, FORM_block2),
        (KEY_enabled, FORM_flag),
        (KEY_lot, FORM_lot),
    ]
    mordant = [(KEY_value, FORM_sleb)]
    defs = [
        dyeworksdef(1, TYPE_city, 1, w),
        dyeworksdef(5, TYPE_dyeworks, 0, dyeworks),
        dyeworksdef(6, TYPE_booth, 0, mordant),
    ]
    rt.add(0x1111)
    rt.add(0x2222)
    rt.add(0x3333)
    sp = node(
        5,
        dyeworks,
        [(FORM_str, "wide_name"), 8, b"\x01\x02\x03\x04", None, 0x00000001],
        st,
        rt,
    )
    co = node(6, mordant, [-12345], st, rt)
    root = node(1, w, ["mix"], st, rt, children=[sp, co], has_children=True)
    files["valid_009.dye"] = (
        assemble(defs, root, 3, st, rt, version=4),
        summary(4, 3, 3, 1, 1, "range"),
    )

    # 010: a deep tree (range > vat > dyeworks > skein, depth four) whose leaf
    # carries a value reached through an indirect form that resolves to data4.
    st, rt = StrTable(), RuneTable()
    w = [(KEY_name, FORM_str)]
    vat = [(KEY_name, FORM_str)]
    dyeworks = [(KEY_name, FORM_str)]
    eff = [(KEY_index, FORM_indirect)]
    defs = [
        dyeworksdef(1, TYPE_city, 1, w),
        dyeworksdef(2, TYPE_rail, 1, vat),
        dyeworksdef(3, TYPE_dyeworks, 1, dyeworks),
        dyeworksdef(4, TYPE_car, 0, eff),
    ]
    ef = node(4, eff, [(FORM_data4, 0x12345678)], st, rt)
    sp = node(3, dyeworks, ["bolt"], st, rt, children=[ef], has_children=True)
    ti = node(2, vat, ["adept"], st, rt, children=[sp], has_children=True)
    root = node(1, w, ["deep"], st, rt, children=[ti], has_children=True)
    files["valid_010.dye"] = (
        assemble(defs, root, 4, st, rt, version=4),
        summary(4, 4, 4, 0, 1, "range"),
    )

    return files


# ---------------------------------------------------------------------------
# Exploit corpus.
# ---------------------------------------------------------------------------
def simple_sections():
    """A small, well-formed set of four section blobs reused by exploits that
    target a later stage."""
    st, rt = StrTable(), RuneTable()
    w = [(KEY_name, FORM_str)]
    defs = [dyeworksdef(1, TYPE_city, 0, w)]
    nodes = node(1, w, ["ok.dye"], st, rt)
    return {
        SEC_DYEWORKSDEFS: dyeworksdef_section(defs),
        SEC_NODES: nodes_section(4, 0, 8, 1, nodes),
        SEC_LOTS: rt.blob(),
        SEC_STR: bytes(st.blob),
    }


def build_exploits():
    files = {}

    # sectab: the dyeworksdefs section is declared far outside the file, so reading
    # it lands out of bounds.
    secs = simple_sections()
    files["exploit_sectab.dye"] = container(
        secs, overrides={SEC_DYEWORKSDEFS: (0x40000000, 4)}
    )

    # uleb: a varint made of continuation bytes runs off the end of the dyeworksdefs
    # section, which sits at the end of the file.
    st, rt = StrTable(), RuneTable()
    bad = uleb(1) + b"\x80" * 6  # code 1, then a never-ending type varint
    secs = {
        SEC_NODES: nodes_section(4, 0, 8, 0, b""),
        SEC_STR: bytes(st.blob),
        SEC_LOTS: rt.blob(),
        SEC_DYEWORKSDEFS: bad,
    }
    files["exploit_uleb.dye"] = container(
        secs, order=(SEC_NODES, SEC_STR, SEC_LOTS, SEC_DYEWORKSDEFS)
    )

    # dyeworksdef (truncated): a declaration whose has-children byte falls just past
    # the dyeworksdefs section, which ends at the end of the file.
    st, rt = StrTable(), RuneTable()
    bad = uleb(1) + uleb(TYPE_city)  # code + type, nothing after
    secs = {
        SEC_NODES: nodes_section(4, 0, 8, 0, b""),
        SEC_STR: bytes(st.blob),
        SEC_LOTS: rt.blob(),
        SEC_DYEWORKSDEFS: bad,
    }
    files["exploit_dyeworksdeftrunc.dye"] = container(
        secs, order=(SEC_NODES, SEC_STR, SEC_LOTS, SEC_DYEWORKSDEFS)
    )

    # dyeworksdef (lookup): a node names a type code that is not in the dyeworksdefs.
    st, rt = StrTable(), RuneTable()
    w = [(KEY_name, FORM_str)]
    defs = [dyeworksdef(1, TYPE_city, 0, w)]
    nodes = uleb(99)  # code 99 is undeclared
    secs = {
        SEC_DYEWORKSDEFS: dyeworksdef_section(defs),
        SEC_NODES: nodes_section(4, 0, 8, 1, nodes),
        SEC_LOTS: rt.blob(),
        SEC_STR: bytes(st.blob),
    }
    files["exploit_dyeworksdef.dye"] = container(secs)

    # node (unit): a unit length that claims the unit extends past the nodes
    # section drives the node walk off the end of the file.
    st, rt = StrTable(), RuneTable()
    defs = [dyeworksdef(1, TYPE_city, 0, [])]
    nodes = uleb(1)  # one real node, no fields
    secs = {
        SEC_DYEWORKSDEFS: dyeworksdef_section(defs),
        SEC_STR: bytes(st.blob),
        SEC_LOTS: rt.blob(),
        SEC_NODES: nodes_section(4, 0, 8, 1, nodes, unit_length_override=0x10000000),
    }
    files["exploit_node.dye"] = container(
        secs, order=(SEC_DYEWORKSDEFS, SEC_STR, SEC_LOTS, SEC_NODES)
    )

    # node (alloc): a node count whose byte size overflows a 32-bit multiply
    # under-allocates the node table the walk then overruns.
    st, rt = StrTable(), RuneTable()
    defs = [dyeworksdef(1, TYPE_city, 0, [])]
    nodes = uleb(1)  # one real node
    secs = {
        SEC_DYEWORKSDEFS: dyeworksdef_section(defs),
        SEC_NODES: nodes_section(4, 0, 8, 1, nodes, node_count_override=0x20000000),
        SEC_LOTS: rt.blob(),
        SEC_STR: bytes(st.blob),
    }
    files["exploit_alloc.dye"] = container(secs)

    # form (block): a block4 length runs the cursor far past the unit, so the
    # following value reads out of bounds.
    st, rt = StrTable(), RuneTable()
    st.add("present")
    p = [(KEY_value, FORM_block4), (KEY_name, FORM_str)]
    defs = [dyeworksdef(1, TYPE_city, 0, p)]
    nodes = uleb(1) + u32(0x10000000) + u32(0)  # block4 length huge, then a str
    secs = {
        SEC_DYEWORKSDEFS: dyeworksdef_section(defs),
        SEC_NODES: nodes_section(4, 0, 8, 1, nodes),
        SEC_LOTS: rt.blob(),
        SEC_STR: bytes(st.blob),
    }
    files["exploit_form.dye"] = container(secs)

    # str: a str offset points far past the end of the strings section.
    st, rt = StrTable(), RuneTable()
    st.add("present")
    p = [(KEY_name, FORM_str)]
    defs = [dyeworksdef(1, TYPE_city, 0, p)]
    nodes = uleb(1) + u32(0x40000000)
    secs = {
        SEC_DYEWORKSDEFS: dyeworksdef_section(defs),
        SEC_NODES: nodes_section(4, 0, 8, 1, nodes),
        SEC_LOTS: rt.blob(),
        SEC_STR: bytes(st.blob),
    }
    files["exploit_str.dye"] = container(secs)

    # lot: a lot index points far past the end of the lots table.
    st, rt = StrTable(), RuneTable()
    rt.add(0x1234)
    p = [(KEY_lot, FORM_lot)]
    defs = [dyeworksdef(1, TYPE_city, 0, p)]
    nodes = uleb(1) + u32(0x40000000)
    secs = {
        SEC_DYEWORKSDEFS: dyeworksdef_section(defs),
        SEC_NODES: nodes_section(4, 0, 8, 1, nodes),
        SEC_LOTS: rt.blob(),
        SEC_STR: bytes(st.blob),
    }
    files["exploit_lot.dye"] = container(secs)

    # uleb (signed): a signed varint made of continuation bytes runs off the end
    # of the nodes section, which sits at the end of the file.
    st, rt = StrTable(), RuneTable()
    p = [(KEY_value, FORM_sleb)]
    defs = [dyeworksdef(1, TYPE_city, 0, p)]
    nodes = uleb(1) + b"\x80" * 6  # code 1, then a never-ending signed varint
    secs = {
        SEC_DYEWORKSDEFS: dyeworksdef_section(defs),
        SEC_STR: bytes(st.blob),
        SEC_LOTS: rt.blob(),
        SEC_NODES: nodes_section(4, 0, 8, 1, nodes),
    }
    files["exploit_sleb.dye"] = container(
        secs, order=(SEC_DYEWORKSDEFS, SEC_STR, SEC_LOTS, SEC_NODES)
    )

    # indirect: a form that redirects to itself recurses without bound, so a long
    # chain of indirect form codes drives the redirection to overflow the stack.
    st, rt = StrTable(), RuneTable()
    p = [(KEY_name, FORM_indirect)]
    defs = [dyeworksdef(1, TYPE_city, 0, p)]
    nodes = uleb(1) + bytes([FORM_indirect]) * 200000  # each redirects to indirect
    secs = {
        SEC_DYEWORKSDEFS: dyeworksdef_section(defs),
        SEC_NODES: nodes_section(4, 0, 8, 1, nodes),
        SEC_LOTS: rt.blob(),
        SEC_STR: bytes(st.blob),
    }
    files["exploit_indirect.dye"] = container(secs)
    # deepnodes: a container node type carrying children nested far deeper than a
    # real tree, so a recursive walk runs the stack off its end unless nesting
    # depth is bounded. The declared node count is larger than the nesting so the
    # node-count guard does not catch it first, leaving the depth bound the only
    # thing standing between the walk and a stack overflow.
    st, rt = StrTable(), RuneTable()
    defs = [dyeworksdef(1, TYPE_city, 1, [])]
    nodes = uleb(1) * 100000 + uleb(0)
    secs = {
        SEC_DYEWORKSDEFS: dyeworksdef_section(defs),
        SEC_NODES: nodes_section(4, 0, 8, 200000, nodes),
        SEC_LOTS: rt.blob(),
        SEC_STR: bytes(st.blob),
    }
    files["exploit_deepnodes.dye"] = container(secs)

    # form (data): a fixed-size data8 value truncated at the unit end, followed
    # by a str. The unpatched reader advances the cursor by the full eight bytes
    # without checking they are present, so the following str read lands out of
    # bounds. The nodes section is placed last so the unit ends at the file end.
    st, rt = StrTable(), RuneTable()
    p = [(KEY_weight, FORM_data8), (KEY_name, FORM_str)]
    defs = [dyeworksdef(1, TYPE_city, 0, p)]
    nodes = uleb(1) + b"\x00\x00" + u32(0)  # two of the eight data8 bytes, then a str
    secs = {
        SEC_DYEWORKSDEFS: dyeworksdef_section(defs),
        SEC_STR: bytes(st.blob),
        SEC_LOTS: rt.blob(),
        SEC_NODES: nodes_section(4, 0, 8, 1, nodes),
    }
    files["exploit_formdata.dye"] = container(
        secs, order=(SEC_DYEWORKSDEFS, SEC_STR, SEC_LOTS, SEC_NODES)
    )

    # form (string): an inline string with no terminating NUL runs to the end of
    # the unit, so the unpatched scan walks past the unit and off the buffer.
    st, rt = StrTable(), RuneTable()
    p = [(KEY_label, FORM_string)]
    defs = [dyeworksdef(1, TYPE_city, 0, p)]
    nodes = uleb(1) + b"\xaa" * 8  # inline string bytes, never a NUL
    secs = {
        SEC_DYEWORKSDEFS: dyeworksdef_section(defs),
        SEC_STR: bytes(st.blob),
        SEC_LOTS: rt.blob(),
        SEC_NODES: nodes_section(4, 0, 8, 1, nodes),
    }
    files["exploit_formstring.dye"] = container(
        secs, order=(SEC_DYEWORKSDEFS, SEC_STR, SEC_LOTS, SEC_NODES)
    )

    # form (block1 length): the one-byte block length field sits exactly at the
    # end of the unit, so the unpatched reader reads the length past the buffer.
    st, rt = StrTable(), RuneTable()
    p = [(KEY_data, FORM_block1)]
    defs = [dyeworksdef(1, TYPE_city, 0, p)]
    nodes = uleb(1)  # code only; the block1 length byte would sit past the unit
    secs = {
        SEC_DYEWORKSDEFS: dyeworksdef_section(defs),
        SEC_STR: bytes(st.blob),
        SEC_LOTS: rt.blob(),
        SEC_NODES: nodes_section(4, 0, 8, 1, nodes),
    }
    files["exploit_formblock1len.dye"] = container(
        secs, order=(SEC_DYEWORKSDEFS, SEC_STR, SEC_LOTS, SEC_NODES)
    )

    # form (block1 body): a one-byte block length claims more bytes than the unit
    # holds, followed by a str, so the unpatched reader advances past the body and
    # the str read lands out of bounds.
    st, rt = StrTable(), RuneTable()
    p = [(KEY_data, FORM_block1), (KEY_name, FORM_str)]
    defs = [dyeworksdef(1, TYPE_city, 0, p)]
    nodes = uleb(1) + b"\xff" + u32(0)  # block1 length 255 with no body, then a str
    secs = {
        SEC_DYEWORKSDEFS: dyeworksdef_section(defs),
        SEC_STR: bytes(st.blob),
        SEC_LOTS: rt.blob(),
        SEC_NODES: nodes_section(4, 0, 8, 1, nodes),
    }
    files["exploit_formblock1body.dye"] = container(
        secs, order=(SEC_DYEWORKSDEFS, SEC_STR, SEC_LOTS, SEC_NODES)
    )

    # form (block2 length): only one of the two block-length bytes is present
    # before the unit ends, so the unpatched two-byte length read runs off the end.
    st, rt = StrTable(), RuneTable()
    p = [(KEY_data, FORM_block2)]
    defs = [dyeworksdef(1, TYPE_city, 0, p)]
    nodes = uleb(1) + b"\x00"  # code + one of the two length bytes
    secs = {
        SEC_DYEWORKSDEFS: dyeworksdef_section(defs),
        SEC_STR: bytes(st.blob),
        SEC_LOTS: rt.blob(),
        SEC_NODES: nodes_section(4, 0, 8, 1, nodes),
    }
    files["exploit_formblock2len.dye"] = container(
        secs, order=(SEC_DYEWORKSDEFS, SEC_STR, SEC_LOTS, SEC_NODES)
    )

    # form (block2 body): a two-byte block length claims far more bytes than the
    # unit holds, followed by a str, so the unpatched reader advances past the body
    # and the str read lands out of bounds.
    st, rt = StrTable(), RuneTable()
    p = [(KEY_data, FORM_block2), (KEY_name, FORM_str)]
    defs = [dyeworksdef(1, TYPE_city, 0, p)]
    nodes = uleb(1) + u16(0xFFFF) + u32(0)  # block2 length 65535 with no body, then a str
    secs = {
        SEC_DYEWORKSDEFS: dyeworksdef_section(defs),
        SEC_STR: bytes(st.blob),
        SEC_LOTS: rt.blob(),
        SEC_NODES: nodes_section(4, 0, 8, 1, nodes),
    }
    files["exploit_formblock2body.dye"] = container(
        secs, order=(SEC_DYEWORKSDEFS, SEC_STR, SEC_LOTS, SEC_NODES)
    )

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
