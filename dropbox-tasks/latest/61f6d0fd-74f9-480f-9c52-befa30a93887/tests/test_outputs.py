"""Verifier for dyeworksmini-c-dyeworks-tree-parser.

Builds the agent's tree and runs the binary against the valid corpus and a
held-back exploit corpus that ships beside this verifier, never inside the
agent's environment. Several planted memory-safety bugs across the section
table, the LEB128 decoder, the dyeworksdef table, the unit header, the node walk,
the form decoder, the strings resolver, the lots resolver, and the node-table
allocation must all be fixed by audit, and the recursive consume of an indirect
param value must be guarded so a run of indirect forms cannot run the stack off
its end. Every held-back exploit must reject through a clean logic error path: a
crash while handling one (a segfault, a heap over-read, or a stack overflow)
means the bug is still live, so no crash signature may appear in stderr and the
rejection must come through the program's own per-subsystem error path. The
valid corpus includes a param value reached through an indirect form that names
a concrete form, which a fix that refuses every indirect value rather than only
the self-naming one would wrongly reject.
"""

import hashlib
import json
import os
import resource
import struct
import subprocess
from pathlib import Path

import pytest

ENV = Path("/app/environment")
BINARY = ENV / "dyeworks"
VALID = ENV / "testdata" / "valid"
EXPLOITS = Path(__file__).resolve().parent / "exploits"

# A correct fix may guard the malformed input at any layer of the parse graph,
# so a clean rejection naming any of the program's subsystems is accepted. The
# runtime crash-absence check is what proves the specific bug is fixed: an
# unfixed bug still faults on its exploit.
SUBSYS = (
    "header",
    "sectab",
    "uleb",
    "dyeworksdef",
    "node",
    "form",
    "lot",
    "str",
    "format",
)

CRASH_SIGNATURES = (
    "addresssanitizer",
    "heap-buffer-overflow",
    "stack-buffer-overflow",
    "heap-use-after-free",
    "negative-size-param",
    "==error==",
    "shadow bytes around",
    "summary: addresssanitizer",
    "sanitizer",
    "segmentation fault",
    "sigsegv",
    "sigabrt",
    "sigbus",
    "sigfpe",
    "floating point exception",
    "core dumped",
    "stack smashing",
    "fatal glibc",
    "malloc(): ",
    "free(): ",
    "double free",
    "corrupted",
)


# Cap each child's address space below the container's memory budget so a
# hostile file that drives a runaway allocation (for example a node count whose
# byte size is "fixed" by widening to size_t instead of being rejected) faults
# inside the child instead of OOM-killing the whole verifier session. The cap
# is far above anything the legitimate corpus needs and well under memory_mb.
_ADDR_LIMIT = 1536 * 1024 * 1024


def _cap_child():
    resource.setrlimit(resource.RLIMIT_AS, (_ADDR_LIMIT, _ADDR_LIMIT))


def run(cmd: list, timeout: int = 120, cwd: Path = ENV) -> subprocess.CompletedProcess:
    """Run a command with byte-precise guard pages."""
    env = dict(os.environ)
    env["EF_DISABLE_BANNER"] = "1"
    env["EF_ALIGNMENT"] = "1"
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        env=env,
        preexec_fn=_cap_child,
    )


def assert_clean_rejection(r: subprocess.CompletedProcess, name: str) -> None:
    """Assert a hostile input was rejected by logic: nonzero exit, a known
    subsystem named in stderr, and no crash (sanitizer abort, segfault, heap
    corruption, or stack overflow)."""
    err = r.stderr.lower()
    assert r.returncode != 0, f"{name} was accepted (exit 0); it must be rejected"
    assert r.returncode > 0, (
        f"{name} was killed by a signal (rc={r.returncode}); the bug is still "
        f"live.\nstderr:\n{r.stderr}"
    )
    for sig in CRASH_SIGNATURES:
        assert sig not in err, (
            f"{name} was rejected by a crash, not a clean logic check; the bug "
            f"is still live.\nstderr:\n{r.stderr}"
        )
    assert any(sub in err for sub in SUBSYS), (
        f"{name} was rejected but its stderr names no known subsystem; the "
        f"rejection must name the path it caught.\nstderr:\n{r.stderr}"
    )


@pytest.fixture(scope="session")
def built():
    """Compile the agent's tree once per session."""
    run(["make", "clean"])
    r = run(["make"], timeout=300)
    assert r.returncode == 0, f"make failed:\n{r.stdout}\n{r.stderr}"
    assert BINARY.exists(), "build did not produce the dyeworks binary"
    return BINARY


def parse(fixture: Path) -> subprocess.CompletedProcess:
    """Run the built binary against one fixture."""
    return run([str(BINARY), str(fixture)])


VALID_SUMMARY = {
    "valid_001.dye": {
        "version": 4,
        "dyeworksdefs_defined": 1,
        "nodes_parsed": 1,
        "lots_resolved": 0,
        "indirects_resolved": 0,
        "root_type": "range",
    },
    "valid_002.dye": {
        "version": 4,
        "dyeworksdefs_defined": 2,
        "nodes_parsed": 2,
        "lots_resolved": 0,
        "indirects_resolved": 0,
        "root_type": "range",
    },
    "valid_003.dye": {
        "version": 5,
        "dyeworksdefs_defined": 3,
        "nodes_parsed": 3,
        "lots_resolved": 0,
        "indirects_resolved": 0,
        "root_type": "range",
    },
    "valid_004.dye": {
        "version": 4,
        "dyeworksdefs_defined": 2,
        "nodes_parsed": 2,
        "lots_resolved": 0,
        "indirects_resolved": 0,
        "root_type": "range",
    },
    "valid_005.dye": {
        "version": 4,
        "dyeworksdefs_defined": 3,
        "nodes_parsed": 3,
        "lots_resolved": 0,
        "indirects_resolved": 0,
        "root_type": "range",
    },
    "valid_006.dye": {
        "version": 4,
        "dyeworksdefs_defined": 1,
        "nodes_parsed": 1,
        "lots_resolved": 0,
        "indirects_resolved": 0,
        "root_type": "range",
    },
    "valid_007.dye": {
        "version": 4,
        "dyeworksdefs_defined": 1,
        "nodes_parsed": 1,
        "lots_resolved": 0,
        "indirects_resolved": 0,
        "root_type": "range",
    },
    "valid_008.dye": {
        "version": 4,
        "dyeworksdefs_defined": 2,
        "nodes_parsed": 2,
        "lots_resolved": 0,
        "indirects_resolved": 0,
        "root_type": "range",
    },
    "valid_009.dye": {
        "version": 4,
        "dyeworksdefs_defined": 3,
        "nodes_parsed": 3,
        "lots_resolved": 1,
        "indirects_resolved": 1,
        "root_type": "range",
    },
    "valid_010.dye": {
        "version": 4,
        "dyeworksdefs_defined": 4,
        "nodes_parsed": 4,
        "lots_resolved": 0,
        "indirects_resolved": 1,
        "root_type": "range",
    },
}


# The one-line JSON summary of a well-formed file must carry exactly these keys
# in this order, and nothing else.
KEY_ORDER = [
    "version",
    "dyeworksdefs_defined",
    "nodes_parsed",
    "lots_resolved",
    "indirects_resolved",
    "root_type",
]

# The baseline valid corpus is pinned by content hash so the regression cannot be
# skipped by deleting or altering a fixture: the fixtures are writable in the
# agent's environment, but the verifier holds their expected bytes here.
VALID_SHA256 = {
    "valid_001.dye": "75a3d7102ba956d00908d33448d3606f74bd4bdf04ee04695cd3906e460668ae",
    "valid_002.dye": "3bc415c2e0dd9bfa638afd83e8712e13e83afab2de4c43e3579f0b53198a396c",
    "valid_003.dye": "ac6c3173cf0140ed341dcabe706911a177da0150bae4d816db70ed88bb50bccb",
    "valid_004.dye": "f21c78ca2f575adefbaf7afa5e62c3a07e582c96cc9faae710ddfe8d028fcd37",
    "valid_005.dye": "2c2cc66ba750d079a8e70af2a64117ec36e333a10459e4a1475ae77d0a0beb17",
    "valid_006.dye": "3a110b1162e838a88809d33e07f4a5e8e820c90583665a41f651ec034e7b8f78",
    "valid_007.dye": "b6230d29a84ab37ec53b410e2258ab2cbb31f475263a2699a05650142d099130",
    "valid_008.dye": "9bd0d4296f8a511856a6d71ef2b4be720fc8e82e597e7da5c33dc326d88c88fa",
    "valid_009.dye": "dcc78a32254ce2245714b5ab5310859cbd4e7162c7c116d7239c20fa9a6fd0d6",
    "valid_010.dye": "520d83ee1a1e6ef4a7ee9898bf2711bc2cb6a3a6cb793b250e4fcf6070f691d3",
}


def _assert_one_json_line(name, stdout):
    """The reader must print exactly one line whose only content is the summary
    JSON object, with the documented keys in the documented order and nothing
    else: no extra keys, no reordering, no additional lines."""
    lines = stdout.splitlines()
    assert len(lines) == 1, f"{name}: output is not a single line: {stdout!r}"
    keys = list(json.loads(lines[0]).keys())
    assert keys == KEY_ORDER, (
        f"{name}: JSON keys {keys} are not exactly {KEY_ORDER} in that order"
    )


def _check_summary(name, r):
    assert r.returncode == 0, f"{name} was rejected by the patched parser:\n{r.stderr}"
    assert r.stderr == "", (
        f"{name} parsed but wrote to stderr; a well-formed file must print "
        f"nothing on stderr.\nstderr:\n{r.stderr}"
    )
    _assert_one_json_line(name, r.stdout)
    summary = json.loads(r.stdout)
    for key, want in VALID_SUMMARY[name].items():
        assert summary.get(key) == want, (
            f"{name}: {key}={summary.get(key)} disagrees with the known "
            f"value ({key}={want})"
        )


def test_valid_corpus_is_intact():
    """The baseline valid corpus must be exactly the expected fixture set with the
    expected bytes; deleting or altering one must not let the regression loop pass
    silently."""
    present = sorted(p.name for p in VALID.glob("*.dye"))
    assert present == sorted(VALID_SHA256), (
        f"valid corpus fixture set changed: found {present}, expected "
        f"{sorted(VALID_SHA256)}"
    )
    for name, want in VALID_SHA256.items():
        got = hashlib.sha256((VALID / name).read_bytes()).hexdigest()
        assert got == want, f"{name} content changed (sha256 {got} != {want})"


def test_valid_corpus_parses_cleanly(built):
    """Every baseline valid file must exist and parse to its true summary."""
    for name in ("valid_001.dye", "valid_002.dye", "valid_003.dye",
                 "valid_004.dye", "valid_005.dye"):
        p = VALID / name
        assert p.exists(), f"valid fixture {name} is missing"
        _check_summary(name, parse(p))


def test_exploit_sectab_rejected(built):
    """A section declared outside the file must be rejected, not chased."""
    assert_clean_rejection(parse(EXPLOITS / "exploit_sectab.dye"), "exploit_sectab.dye")


def test_exploit_uleb_rejected(built):
    """A varint that runs off the end of a section must be rejected."""
    assert_clean_rejection(parse(EXPLOITS / "exploit_uleb.dye"), "exploit_uleb.dye")


def test_exploit_dyeworksdeftrunc_rejected(built):
    """A declaration with no terminating bytes must be rejected."""
    assert_clean_rejection(
        parse(EXPLOITS / "exploit_dyeworksdeftrunc.dye"), "exploit_dyeworksdeftrunc.dye"
    )


def test_exploit_dyeworksdef_rejected(built):
    """A node naming an undeclared type code must be rejected."""
    assert_clean_rejection(
        parse(EXPLOITS / "exploit_dyeworksdef.dye"), "exploit_dyeworksdef.dye"
    )


def test_exploit_node_rejected(built):
    """A unit length that overruns the nodes section must be rejected."""
    assert_clean_rejection(parse(EXPLOITS / "exploit_node.dye"), "exploit_node.dye")


def test_exploit_alloc_rejected(built):
    """A node count whose byte size overflows must be rejected."""
    assert_clean_rejection(parse(EXPLOITS / "exploit_alloc.dye"), "exploit_alloc.dye")


def test_exploit_form_rejected(built):
    """A block length that runs the cursor past the unit must be rejected."""
    assert_clean_rejection(parse(EXPLOITS / "exploit_form.dye"), "exploit_form.dye")


def test_exploit_str_rejected(built):
    """A str offset outside the strings section must be rejected."""
    assert_clean_rejection(parse(EXPLOITS / "exploit_str.dye"), "exploit_str.dye")


def test_exploit_formdata_rejected(built):
    """A fixed-size data value truncated at the unit end must be rejected, not
    consumed by advancing the cursor over bytes the unit does not hold."""
    assert_clean_rejection(
        parse(EXPLOITS / "exploit_formdata.dye"), "exploit_formdata.dye"
    )


def test_exploit_formstring_rejected(built):
    """An inline string with no terminating NUL must be rejected at the unit
    boundary, not scanned off the end of the buffer."""
    assert_clean_rejection(
        parse(EXPLOITS / "exploit_formstring.dye"), "exploit_formstring.dye"
    )


def test_exploit_formblock1len_rejected(built):
    """A one-byte block length field sitting past the unit end must be rejected
    before it is read."""
    assert_clean_rejection(
        parse(EXPLOITS / "exploit_formblock1len.dye"), "exploit_formblock1len.dye"
    )


def test_exploit_formblock1body_rejected(built):
    """A one-byte block length claiming more bytes than the unit holds must be
    rejected, not consumed past the unit end."""
    assert_clean_rejection(
        parse(EXPLOITS / "exploit_formblock1body.dye"), "exploit_formblock1body.dye"
    )


def test_exploit_formblock2len_rejected(built):
    """A two-byte block length field truncated at the unit end must be rejected
    before it is read."""
    assert_clean_rejection(
        parse(EXPLOITS / "exploit_formblock2len.dye"), "exploit_formblock2len.dye"
    )


def test_exploit_formblock2body_rejected(built):
    """A two-byte block length claiming more bytes than the unit holds must be
    rejected, not consumed past the unit end."""
    assert_clean_rejection(
        parse(EXPLOITS / "exploit_formblock2body.dye"), "exploit_formblock2body.dye"
    )


def test_exploit_lot_rejected(built):
    """A lot index outside the lots table must be rejected."""
    assert_clean_rejection(parse(EXPLOITS / "exploit_lot.dye"), "exploit_lot.dye")


def test_exploit_sleb_rejected(built):
    """A signed varint that runs off the end of a section must be rejected."""
    assert_clean_rejection(parse(EXPLOITS / "exploit_sleb.dye"), "exploit_sleb.dye")


def test_exploit_indirect_rejected(built):
    """A long run of indirect form codes must be rejected, not recursed until
    the stack runs off its end."""
    assert_clean_rejection(
        parse(EXPLOITS / "exploit_indirect.dye"), "exploit_indirect.dye"
    )


def test_exploit_deepnodes_rejected(built):
    """A node tree nested far deeper than a real tree must be rejected by a
    bound on nesting depth, not walked recursively until the stack runs off
    its end."""
    r = parse(EXPLOITS / "exploit_deepnodes.dye")
    assert_clean_rejection(r, "exploit_deepnodes.dye")
    assert "node" in r.stderr.lower(), (
        f"exploit_deepnodes.dye must be caught by the node nesting bound "
        f"naming the node subsystem.\nstderr:\n{r.stderr}"
    )


def test_indirect_value_still_parses(built):
    """The valid files whose nodes reach a value through an indirect form that
    names a concrete form must still parse after the indirect guard."""
    for name in ("valid_009.dye", "valid_010.dye"):
        p = VALID / name
        assert p.exists(), f"{name} is missing"
        _check_summary(name, parse(p))


def test_deep_tree_still_parses(built):
    """The deep nested tree must keep parsing after the bounds checks. A fix
    that treats reaching the unit end as an error rather than a closed chain
    would wrongly reject it."""
    r = parse(VALID / "valid_010.dye")
    assert r.returncode == 0, (
        f"valid_010.dye (deep tree) was rejected; the fix is too "
        f"aggressive.\nstderr:\n{r.stderr}"
    )
    summary = json.loads(r.stdout)
    assert summary.get("nodes_parsed") == 4, (
        f"valid_010.dye nodes_parsed={summary.get('nodes_parsed')} disagrees "
        f"with the known value (4)"
    )


def test_lot_ref_still_resolves(built):
    """A valid lot reference into the lots table must still resolve after the
    lot bounds check, not be refused wholesale."""
    r = parse(VALID / "valid_009.dye")
    assert r.returncode == 0, (
        f"valid_009.dye (lot ref) was rejected; the fix is too "
        f"aggressive.\nstderr:\n{r.stderr}"
    )
    summary = json.loads(r.stdout)
    assert summary.get("lots_resolved") == 1, (
        f"valid_009.dye lots_resolved={summary.get('lots_resolved')} "
        f"disagrees with the known value (1)"
    )


def test_boundary_valid_files_still_parse(built):
    """Boundary-case valid files must still parse despite the bounds checks."""
    for name in ("valid_006.dye", "valid_007.dye", "valid_008.dye"):
        p = VALID / name
        assert p.exists(), f"boundary fixture {name} is missing"
        _check_summary(name, parse(p))


# ---------------------------------------------------------------------------
# Generated-at-test-time fixtures: a valid file the agent has never seen must
# parse, and a freshly minted out-of-bounds file must reject cleanly. This
# guards against a fix that special-cases the shipped corpus byte-for-byte.
# ---------------------------------------------------------------------------
def _u16(v):
    return struct.pack(">H", v & 0xFFFF)


def _u32(v):
    return struct.pack(">I", v & 0xFFFFFFFF)


def _uleb(v):
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


def _mint(str_offset):
    """Build a one-node range file whose name str points at *str_offset*."""
    dyeworksdefs = (
        _uleb(1)
        + _uleb(0x01)
        + b"\x00"
        + _uleb(0x01)
        + _uleb(0x07)
        + _uleb(0)
        + _uleb(0)
        + _uleb(0)
    )
    strings = b"gen\x00"
    lots = b""
    node_bytes = _uleb(1) + _u32(str_offset)
    body = _u16(4) + _u32(0) + b"\x08" + _u32(1) + node_bytes
    nodes = _u32(len(body)) + body

    header = b"DYEW" + bytes([1, 4, 0, 0])
    cursor = 8 + 4 * 9
    sections = [(0, dyeworksdefs), (1, nodes), (2, lots), (3, strings)]
    table = bytearray()
    body_out = bytearray()
    for name, blob in sections:
        table += bytes([name]) + _u32(cursor) + _u32(len(blob))
        body_out += blob
        cursor += len(blob)
    return header + bytes(table) + bytes(body_out)


def test_generated_valid_parses(built, tmp_path):
    """A freshly generated valid file must parse cleanly."""
    p = tmp_path / "gen_valid.dye"
    p.write_bytes(_mint(0))
    r = parse(p)
    assert r.returncode == 0, f"generated valid file was rejected:\n{r.stderr}"
    summary = json.loads(r.stdout)
    assert summary.get("root_type") == "range"
    assert summary.get("nodes_parsed") == 1


def test_generated_oob_str_rejected(built, tmp_path):
    """A freshly generated file whose str offset is far past the strings
    section must reject cleanly, not crash."""
    p = tmp_path / "gen_oob.dye"
    p.write_bytes(_mint(0x40000000))
    assert_clean_rejection(parse(p), "gen_oob.dye")


def _mint_form(form_code, value_bytes, unit_len=None):
    """Build a one-node range file whose single param uses *form_code* carrying
    *value_bytes*. When *unit_len* is smaller than the natural unit length the
    value runs past the unit end while its bytes still sit inside the file, so a
    reader that does not prove the value fits the unit reads past the unit."""
    dyeworksdefs = (
        _uleb(1) + _uleb(0x01) + b"\x00" + _uleb(0x01) + _uleb(form_code)
        + _uleb(0) + _uleb(0) + _uleb(0)
    )
    strings = b"gen\x00"
    lots = _u32(0)   # one lot id, so a well-formed ref would resolve
    node_bytes = _uleb(1) + value_bytes
    prefix = _u16(4) + _u32(0) + b"\x08" + _u32(1)
    unit_body = prefix + node_bytes
    if unit_len is None:
        unit_len = len(unit_body)
    nodes = _u32(unit_len) + unit_body
    header = b"DYEW" + bytes([1, 4, 0, 0])
    cursor = 8 + 4 * 9
    sections = [(0, dyeworksdefs), (1, nodes), (2, lots), (3, strings)]
    table = bytearray()
    body_out = bytearray()
    for nm, blob in sections:
        table += bytes([nm]) + _u32(cursor) + _u32(len(blob))
        body_out += blob
        cursor += len(blob)
    return header + bytes(table) + bytes(body_out)


# label, form code, value bytes present, unit_length that ends one byte before the
# value read completes so the form is proven not to fit the unit.
_FORM_TRUNCATIONS = [
    ("data1", 0x01, b"\x00", 12),
    ("data2", 0x02, b"\x00\x00", 13),
    ("data4", 0x03, b"\x00\x00\x00\x00", 15),
    ("block4len", 0x0b, b"\x00\x00\x00\x00", 13),
    ("str", 0x07, b"\x00\x00\x00\x00", 15),
    ("lot", 0x11, b"\x00\x00\x00\x00", 15),
]


@pytest.mark.parametrize("label,form,value,unit_len", _FORM_TRUNCATIONS)
def test_generated_form_truncation_rejected(
    built, tmp_path, label, form, value, unit_len
):
    """Every fixed-width or length-prefixed form value must be proven to fit the
    unit before it is read. A file whose unit ends inside the value must be
    refused cleanly, not read past the unit end."""
    p = tmp_path / f"gen_form_{label}.dye"
    p.write_bytes(_mint_form(form, value, unit_len))
    assert_clean_rejection(parse(p), f"gen_form_{label}.dye")


def test_generated_uleb_overflow_rejected(built, tmp_path):
    """A ULEB param value whose tenth group carries bits past bit 63 does not fit
    a uint64 and must be refused, not decoded with its high bits silently lost."""
    p = tmp_path / "gen_uleb_overflow.dye"
    p.write_bytes(_mint_form(0x05, b"\x80" * 9 + b"\x02"))
    assert_clean_rejection(parse(p), "gen_uleb_overflow.dye")


def test_generated_sleb_overflow_rejected(built, tmp_path):
    """An SLEB param value whose tenth group is neither an all-zero nor an all-one
    sign extension overflows a signed 64-bit value and must be refused."""
    p = tmp_path / "gen_sleb_overflow.dye"
    p.write_bytes(_mint_form(0x06, b"\x80" * 9 + b"\x02"))
    assert_clean_rejection(parse(p), "gen_sleb_overflow.dye")


def test_generated_indirect_names_indirect_rejected(built, tmp_path):
    """An indirect form names a concrete form; a value that chains indirect to
    indirect is malformed and must be refused."""
    p = tmp_path / "gen_indirect2.dye"
    p.write_bytes(_mint_form(0x10, _uleb(0x10)))
    assert_clean_rejection(parse(p), "gen_indirect2.dye")


def test_generated_unterminated_string_rejected(built, tmp_path):
    """A str offset that is in range but whose entry has no terminating NUL before
    the end of the strings section must be refused, not walked past the section."""
    dyeworksdefs = (
        _uleb(1) + _uleb(0x01) + b"\x00" + _uleb(0x01) + _uleb(0x07)
        + _uleb(0) + _uleb(0) + _uleb(0)
    )
    strings = b"AAAA"          # no terminating NUL
    lots = b""
    node_bytes = _uleb(1) + _u32(0)   # str offset 0 into "AAAA"
    body = _u16(4) + _u32(0) + b"\x08" + _u32(1) + node_bytes
    nodes = _u32(len(body)) + body
    header = b"DYEW" + bytes([1, 4, 0, 0])
    cursor = 8 + 4 * 9
    sections = [(0, dyeworksdefs), (1, nodes), (2, lots), (3, strings)]
    table = bytearray()
    body_out = bytearray()
    for nm, blob in sections:
        table += bytes([nm]) + _u32(cursor) + _u32(len(blob))
        body_out += blob
        cursor += len(blob)
    p = tmp_path / "gen_unterm_str.dye"
    p.write_bytes(header + bytes(table) + bytes(body_out))
    assert_clean_rejection(parse(p), "gen_unterm_str.dye")


def _mint_leaf_unit(node_bytes, node_count=1, cdef_offset=0, has_children=False):
    """One declared type (code 1, no fields) whose nodes are bare type codes, so
    the unit header and node-count checks can be exercised without form values."""
    dyeworksdefs = (
        _uleb(1) + _uleb(0x01) + (b"\x01" if has_children else b"\x00")
        + _uleb(0) + _uleb(0) + _uleb(0)
    )
    strings = b"gen\x00"
    lots = b""
    body = _u16(4) + _u32(cdef_offset) + b"\x08" + _u32(node_count) + node_bytes
    nodes = _u32(len(body)) + body
    header = b"DYEW" + bytes([1, 4, 0, 0])
    cursor = 8 + 4 * 9
    sections = [(0, dyeworksdefs), (1, nodes), (2, lots), (3, strings)]
    table = bytearray()
    body_out = bytearray()
    for nm, blob in sections:
        table += bytes([nm]) + _u32(cursor) + _u32(len(blob))
        body_out += blob
        cursor += len(blob)
    return header + bytes(table) + bytes(body_out)


def test_generated_bad_dyeworksdef_offset_rejected(built, tmp_path):
    """A unit whose dyeworksdef_offset points outside the dyeworksdef section must be
    refused, not used to index that section out of range."""
    p = tmp_path / "gen_cdefoff.dye"
    p.write_bytes(_mint_leaf_unit(_uleb(1), node_count=1, cdef_offset=0xFFFFFFFF))
    assert_clean_rejection(parse(p), "gen_cdefoff.dye")


def test_generated_more_nodes_than_count_rejected(built, tmp_path):
    """A unit that holds more real nodes than its node_count declares must be
    refused, not written past the node table."""
    p = tmp_path / "gen_nodecount.dye"
    p.write_bytes(_mint_leaf_unit(_uleb(1) + _uleb(1), node_count=1))
    assert_clean_rejection(parse(p), "gen_nodecount.dye")


def test_generated_missing_child_terminator_rejected(built, tmp_path):
    """A container node whose child chain reaches the unit end without a null
    terminator is malformed and must be refused."""
    p = tmp_path / "gen_noterm.dye"
    p.write_bytes(_mint_leaf_unit(_uleb(1), node_count=4, has_children=True))
    assert_clean_rejection(parse(p), "gen_noterm.dye")


# ---------------------------------------------------------------------------
# Boundary fixtures for the two limits the format fixes — the 256-level node
# nesting bound and the 64 MiB whole-container bound — and for the three
# distinct varint failure modes (truncation, over-long encoding, numeric
# overflow). Each limit is exercised at its edge: the largest conforming value
# must still parse and the first nonconforming value must reject cleanly.
# ---------------------------------------------------------------------------

# The whole-container size limit, matching DYEWORKS_MAX_FILE in the reader.
DYEWORKS_MAX_FILE = 64 * 1024 * 1024

# The byte length of the single no-field leaf declaration _mint_leaf_unit emits,
# so a unit can name an dyeworksdef offset exactly at the section's end.
_LEAF_DYEWORKSDEFS_LEN = len(
    _uleb(1) + _uleb(0x01) + b"\x00" + _uleb(0) + _uleb(0) + _uleb(0)
)


def _nested_nodes(depth):
    """Node bytes for a linear chain of *depth* container nodes, each nested in
    the previous. Every node uses type code 1 (a container with children and no
    fields); each child chain is closed by an explicit null node, and the
    innermost holds only its closing null."""
    nb = _uleb(1) + _uleb(0)  # innermost container: code, then its null child chain
    for _ in range(depth - 1):
        nb = _uleb(1) + nb + _uleb(0)  # wrap: code, inner chain, closing null
    return nb


def _mint_sized(total):
    """A conforming one-node range file padded with unreferenced NUL strings to
    exactly *total* bytes, so the whole-container size limit can be exercised at
    its boundary. The padding lives in the strings section, which the reader
    only walks where a str offset names it."""
    dyeworksdefs = (
        _uleb(1) + _uleb(0x01) + b"\x00" + _uleb(0x01) + _uleb(0x07)
        + _uleb(0) + _uleb(0) + _uleb(0)
    )
    lots = b""
    node_bytes = _uleb(1) + _u32(0)
    body = _u16(4) + _u32(0) + b"\x08" + _u32(1) + node_bytes
    nodes = _u32(len(body)) + body
    header = b"DYEW" + bytes([1, 4, 0, 0])
    prefix_len = 8 + 4 * 9 + len(dyeworksdefs) + len(nodes) + len(lots)
    strings = b"gen\x00"
    pad = total - prefix_len - len(strings)
    if pad < 0:
        raise ValueError("target size smaller than the base file")
    strings = strings + b"\x00" * pad
    cursor = 8 + 4 * 9
    sections = [(0, dyeworksdefs), (1, nodes), (2, lots), (3, strings)]
    table = bytearray()
    body_out = bytearray()
    for nm, blob in sections:
        table += bytes([nm]) + _u32(cursor) + _u32(len(blob))
        body_out += blob
        cursor += len(blob)
    return header + bytes(table) + bytes(body_out)


def test_generated_depth_256_nesting_parses(built, tmp_path):
    """A tree nested exactly to the 256-level bound the format fixes must keep
    parsing; a fix that rejects a conforming tree below the bound would fail
    this."""
    p = tmp_path / "gen_depth256.dye"
    p.write_bytes(_mint_leaf_unit(_nested_nodes(256), node_count=256, has_children=True))
    r = parse(p)
    assert r.returncode == 0, (
        f"a tree nested to exactly 256 levels was rejected; the nesting bound is "
        f"too tight.\nstderr:\n{r.stderr}"
    )
    summary = json.loads(r.stdout)
    assert summary.get("nodes_parsed") == 256, (
        f"gen_depth256.dye nodes_parsed={summary.get('nodes_parsed')} disagrees "
        f"with the known value (256)"
    )


def test_generated_depth_257_nesting_rejected(built, tmp_path):
    """A tree nested one level past the 256-level bound must be turned away by
    the node nesting bound naming the node subsystem, not walked recursively
    until the stack runs off its end."""
    p = tmp_path / "gen_depth257.dye"
    p.write_bytes(_mint_leaf_unit(_nested_nodes(257), node_count=512, has_children=True))
    r = parse(p)
    assert_clean_rejection(r, "gen_depth257.dye")
    assert "node" in r.stderr.lower(), (
        f"gen_depth257.dye must be caught by the node nesting bound naming the "
        f"node subsystem.\nstderr:\n{r.stderr}"
    )


def _write_zeros(path, n):
    chunk = b"\x00" * (1024 * 1024)
    with open(path, "wb") as f:
        while n > 0:
            k = min(n, len(chunk))
            f.write(chunk if k == len(chunk) else chunk[:k])
            n -= k


def _write_sized(path, total):
    """Streamed twin of _mint_sized: identical byte layout, but the NUL string
    padding is written in 1 MiB chunks so the verifier never holds the whole
    64 MiB file in memory at once."""
    dyeworksdefs = (
        _uleb(1) + _uleb(0x01) + b"\x00" + _uleb(0x01) + _uleb(0x07)
        + _uleb(0) + _uleb(0) + _uleb(0)
    )
    lots = b""
    node_bytes = _uleb(1) + _u32(0)
    body = _u16(4) + _u32(0) + b"\x08" + _u32(1) + node_bytes
    nodes = _u32(len(body)) + body
    header = b"DYEW" + bytes([1, 4, 0, 0])
    prefix_len = 8 + 4 * 9 + len(dyeworksdefs) + len(nodes) + len(lots)
    strings_prefix = b"gen\x00"
    pad = total - prefix_len - len(strings_prefix)
    if pad < 0:
        raise ValueError("target size smaller than the base file")
    strings_size = len(strings_prefix) + pad
    cursor = 8 + 4 * 9
    lengths = [len(dyeworksdefs), len(nodes), len(lots), strings_size]
    table = bytearray()
    for nm, blen in enumerate(lengths):
        table += bytes([nm]) + _u32(cursor) + _u32(blen)
        cursor += blen
    with open(path, "wb") as f:
        f.write(header + bytes(table) + dyeworksdefs + nodes + lots + strings_prefix)
        chunk = b"\x00" * (1024 * 1024)
        while pad > 0:
            k = min(pad, len(chunk))
            f.write(chunk if k == len(chunk) else chunk[:k])
            pad -= k


def test_generated_max_size_file_parses(built, tmp_path):
    """A conforming container sized to exactly the 64 MiB limit must still
    parse; the limit is the largest size the format admits, not one below it."""
    p = tmp_path / "gen_maxsize.dye"
    _write_sized(p, DYEWORKS_MAX_FILE)
    r = parse(p)
    assert r.returncode == 0, (
        f"a conforming 64 MiB container was rejected; the size limit is one byte "
        f"too tight.\nstderr:\n{r.stderr}"
    )
    summary = json.loads(r.stdout)
    assert summary.get("root_type") == "range"
    assert summary.get("nodes_parsed") == 1


def test_generated_over_max_size_file_rejected(built, tmp_path):
    """A container one byte past the 64 MiB limit must be turned away cleanly by
    the size check, not read into a runaway buffer."""
    p = tmp_path / "gen_oversize.dye"
    _write_zeros(p, DYEWORKS_MAX_FILE + 1)
    assert_clean_rejection(parse(p), "gen_oversize.dye")


def test_generated_dyeworksdef_offset_equals_size_rejected(built, tmp_path):
    """A unit whose dyeworksdef_offset equals the dyeworksdef section size points
    one past the section's last byte and names no declaration, so it must be
    refused just like an offset beyond the section, naming the dyeworksdef
    subsystem."""
    p = tmp_path / "gen_cdefoff_eq.dye"
    p.write_bytes(
        _mint_leaf_unit(_uleb(1), node_count=1, cdef_offset=_LEAF_DYEWORKSDEFS_LEN)
    )
    r = parse(p)
    assert_clean_rejection(r, "gen_cdefoff_eq.dye")
    assert "dyeworksdef" in r.stderr.lower(), (
        f"gen_cdefoff_eq.dye must be caught naming the dyeworksdef subsystem.\n"
        f"stderr:\n{r.stderr}"
    )


def test_generated_uleb_overlong_rejected(built, tmp_path):
    """A ULEB param value spread over more than ten groups is an over-long
    encoding — malformed even though its groups stay inside the unit — and must
    be refused, distinct from a value that overflows 64 bits or one truncated at
    the section end."""
    p = tmp_path / "gen_uleb_overlong.dye"
    p.write_bytes(_mint_form(0x05, b"\x80" * 11 + b"\x00"))
    assert_clean_rejection(parse(p), "gen_uleb_overlong.dye")


def test_generated_sleb_overlong_rejected(built, tmp_path):
    """An SLEB param value spread over more than ten groups is an over-long
    encoding and must be refused, distinct from a signed overflow or a
    truncation."""
    p = tmp_path / "gen_sleb_overlong.dye"
    p.write_bytes(_mint_form(0x06, b"\x80" * 11 + b"\x00"))
    assert_clean_rejection(parse(p), "gen_sleb_overlong.dye")


def test_binary_is_native_elf(built):
    """The audit must produce a native compiled C executable, not a script or a
    wrapper in another language that only imitates the tool."""
    with open(BINARY, "rb") as fh:
        magic = fh.read(4)
    assert magic == b"\x7fELF", (
        f"the dyeworks binary is not a native ELF executable (magic {magic!r}); the "
        f"parser must be compiled C, not a script or a wrapper"
    )
