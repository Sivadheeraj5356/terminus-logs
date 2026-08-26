"""Verifier for the imgscan disk-image reader.

Builds the agent's tree and runs the binary against the valid corpus and a
held-back exploit corpus that ships beside this verifier, never inside the
agent's environment. Several latent memory-safety weaknesses across the
superblock region count, the region-table bounds, the LEB128 decoder, the
inode-table allocation and walk, the volume label resolver, the resident data
run, the hardlink index lookups, and the xattr value scan must all be closed, and the recursive resolve of a directory inode must be bounded so a
crafted chain or a self-referential directory cannot run the stack off its end.
Every held-back exploit must reject through a clean logic error path: a crash
while handling one (a segfault, a heap over-read, or a stack overflow) means the
weakness is still live, so no crash signature may appear in stderr and the rejection
must come through the program's own per-subsystem error path. The valid corpus
includes a directory whose only child is the last inode, a hardlink edge on the
last inode, a deep directory chain, and boundary-packed regions, which a fix that
blanket-refuses these rather than bounding them would wrongly reject.
"""

import json
import os
import struct
import subprocess
from pathlib import Path

import pytest

ENV = Path("/app/environment")
BINARY = ENV / "imgscan"
VALID = ENV / "testdata" / "valid"
EXPLOITS = Path(__file__).resolve().parent / "exploits"

# A correct fix may guard the malformed input at any layer of the parse graph,
# so a clean rejection naming any of the program's subsystems is accepted. The
# runtime crash-absence check is what proves the specific bug is fixed: an
# unfixed bug still faults on its exploit under the guard-page allocator.
SUBSYS = (
    "super",
    "regtab",
    "uleb",
    "vol",
    "inode",
    "name",
    "data",
    "child",
    "link",
    "xattr",
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
    )


def assert_clean_rejection(r: subprocess.CompletedProcess, name: str) -> None:
    """Assert a hostile input was rejected by logic: nonzero exit, a known
    subsystem named in stderr, and no crash (sanitizer abort, segfault, heap
    corruption, or stack overflow)."""
    err = r.stderr.lower()
    assert r.returncode != 0, f"{name} was accepted (exit 0); it must be rejected"
    assert r.returncode > 0, (
        f"{name} was killed by a signal (rc={r.returncode}); the weakness is still "
        f"live.\nstderr:\n{r.stderr}"
    )
    for sig in CRASH_SIGNATURES:
        assert sig not in err, (
            f"{name} was rejected by a crash, not a clean logic check; the weakness "
            f"is still live.\nstderr:\n{r.stderr}"
        )
    assert any(sub in err for sub in SUBSYS), (
        f"{name} was rejected but its stderr names no known subsystem; the "
        f"rejection must name the path it caught.\nstderr:\n{r.stderr}"
    )


def _assert_no_crash(r: subprocess.CompletedProcess, name: str) -> None:
    """Assert a well-formed but adversarial input was handled without a crash. A
    directory chain nested far deeper than any real image is legal but hostile,
    not malformed, so the reader may either resolve it (exit 0, true summary) or
    reject it by a bound (nonzero exit naming a subsystem); either is memory
    safe. Only a signal death or a crash signature fails, meaning the resolver
    still runs the recursion off the stack. A depth limit taken from the inode
    count the file itself declares does not bound the C call stack and still
    overflows here."""
    err = r.stderr.lower()
    assert r.returncode is not None and r.returncode >= 0, (
        f"{name} was killed by a signal (rc={r.returncode}); the directory "
        f"resolver still runs the recursion off the stack.\nstderr:\n{r.stderr}"
    )
    for sig in CRASH_SIGNATURES:
        assert sig not in err, (
            f"{name} crashed rather than handling the deep chain cleanly; the "
            f"resolver still runs the recursion off the stack.\nstderr:\n{r.stderr}"
        )
    if r.returncode != 0:
        assert any(sub in err for sub in SUBSYS), (
            f"{name} exited nonzero but named no known subsystem; a rejection "
            f"must come through the reader's own error path.\nstderr:\n{r.stderr}"
        )


@pytest.fixture(scope="session")
def built():
    """Compile the agent's tree once per session."""
    run(["make", "clean"])
    r = run(["make"], timeout=300)
    assert r.returncode == 0, f"make failed:\n{r.stdout}\n{r.stderr}"
    assert BINARY.exists(), "build did not produce the imgscan binary"
    return BINARY


def parse(fixture: Path) -> subprocess.CompletedProcess:
    """Run the built binary against one fixture."""
    return run([str(BINARY), str(fixture)])


VALID_SUMMARY = {
    "valid_001.dfi": {
        "format_version": 2, "volumes_defined": 1, "inodes_defined": 1,
        "file_inodes": 1, "dir_inodes": 0, "hardlinks_parsed": 0,
        "xattrs_parsed": 0, "data_bytes": 3,
    },
    "valid_002.dfi": {
        "format_version": 2, "volumes_defined": 2, "inodes_defined": 2,
        "file_inodes": 2, "dir_inodes": 0, "hardlinks_parsed": 1,
        "xattrs_parsed": 0, "data_bytes": 2,
    },
    "valid_003.dfi": {
        "format_version": 2, "volumes_defined": 1, "inodes_defined": 3,
        "file_inodes": 2, "dir_inodes": 1, "hardlinks_parsed": 0,
        "xattrs_parsed": 1, "data_bytes": 5,
    },
    "valid_004.dfi": {
        "format_version": 2, "volumes_defined": 1, "inodes_defined": 1,
        "file_inodes": 1, "dir_inodes": 0, "hardlinks_parsed": 0,
        "xattrs_parsed": 0, "data_bytes": 1,
    },
    "valid_005.dfi": {
        "format_version": 2, "volumes_defined": 1, "inodes_defined": 1,
        "file_inodes": 1, "dir_inodes": 0, "hardlinks_parsed": 0,
        "xattrs_parsed": 0, "data_bytes": 4,
    },
    "valid_006.dfi": {
        "format_version": 2, "volumes_defined": 1, "inodes_defined": 3,
        "file_inodes": 2, "dir_inodes": 1, "hardlinks_parsed": 0,
        "xattrs_parsed": 0, "data_bytes": 4,
    },
    "valid_007.dfi": {
        "format_version": 2, "volumes_defined": 1, "inodes_defined": 2,
        "file_inodes": 2, "dir_inodes": 0, "hardlinks_parsed": 1,
        "xattrs_parsed": 0, "data_bytes": 2,
    },
    "valid_008.dfi": {
        "format_version": 2, "volumes_defined": 1, "inodes_defined": 21,
        "file_inodes": 1, "dir_inodes": 20, "hardlinks_parsed": 0,
        "xattrs_parsed": 0, "data_bytes": 2,
    },
    "valid_009.dfi": {
        "format_version": 2, "volumes_defined": 1, "inodes_defined": 1,
        "file_inodes": 1, "dir_inodes": 0, "hardlinks_parsed": 0,
        "xattrs_parsed": 0, "data_bytes": 2,
    },
    "valid_010.dfi": {
        "format_version": 2, "volumes_defined": 1, "inodes_defined": 2,
        "file_inodes": 2, "dir_inodes": 0, "hardlinks_parsed": 1,
        "xattrs_parsed": 1, "data_bytes": 2,
    },
    "valid_011.dfi": {
        "format_version": 2, "volumes_defined": 1, "inodes_defined": 13,
        "file_inodes": 1, "dir_inodes": 12, "hardlinks_parsed": 0,
        "xattrs_parsed": 0, "data_bytes": 4096,
    },
}


def _check_summary(name, r):
    assert r.returncode == 0, f"{name} was rejected by the hardened reader:\n{r.stderr}"
    summary = json.loads(r.stdout)
    for key, want in VALID_SUMMARY[name].items():
        assert summary.get(key) == want, (
            f"{name}: {key}={summary.get(key)} disagrees with the known "
            f"value ({key}={want})"
        )


def test_valid_corpus_parses_cleanly(built):
    """Every baseline valid file must parse and report its true summary."""
    for f in sorted(VALID.glob("valid_00[1-5].dfi")):
        _check_summary(f.name, parse(f))


def test_exploit_super_rejected(built):
    """A region count larger than the table that follows must be rejected."""
    assert_clean_rejection(parse(EXPLOITS / "exploit_super.dfi"), "exploit_super.dfi")


def test_exploit_regtab_rejected(built):
    """A region declared outside the file must be rejected, not chased."""
    assert_clean_rejection(parse(EXPLOITS / "exploit_regtab.dfi"), "exploit_regtab.dfi")


def test_exploit_uleb_rejected(built):
    """A varint that runs off the end of a region must be rejected."""
    assert_clean_rejection(parse(EXPLOITS / "exploit_uleb.dfi"), "exploit_uleb.dfi")


def test_exploit_sleb_rejected(built):
    """A signed varint that runs off the end of a region must be rejected."""
    assert_clean_rejection(parse(EXPLOITS / "exploit_sleb.dfi"), "exploit_sleb.dfi")


def test_exploit_alloc_rejected(built):
    """An inode count whose byte size overflows must be rejected."""
    assert_clean_rejection(parse(EXPLOITS / "exploit_alloc.dfi"), "exploit_alloc.dfi")


def test_exploit_iwalk_rejected(built):
    """An inode read past the end of the inode table must be rejected."""
    assert_clean_rejection(parse(EXPLOITS / "exploit_iwalk.dfi"), "exploit_iwalk.dfi")


def test_exploit_name_rejected(built):
    """A volume label offset outside the names pool must be rejected."""
    assert_clean_rejection(parse(EXPLOITS / "exploit_name.dfi"), "exploit_name.dfi")


def test_exploit_data_rejected(built):
    """A resident data run longer than its region holds must be rejected."""
    assert_clean_rejection(parse(EXPLOITS / "exploit_data.dfi"), "exploit_data.dfi")


def test_exploit_child_rejected(built):
    """A directory child index outside the inode array must be rejected."""
    assert_clean_rejection(parse(EXPLOITS / "exploit_child.dfi"), "exploit_child.dfi")


def test_exploit_deep_no_crash(built):
    """A directory chain nested far deeper than any real image is a legal but
    adversarial file, not a malformed one: the reader must handle it without
    running the call stack off its end. Bounding the nesting depth and rejecting
    the chain, or resolving it without deep recursion, are both memory safe; only
    a crash (a stack overflow) or a hang fails. A cap taken from the inode count
    the file itself declares does not bound the stack and still overflows. If the
    reader resolves the chain it reports the true summary (a single leaf of one
    resident byte)."""
    try:
        r = parse(EXPLOITS / "exploit_deep.dfi")
    except subprocess.TimeoutExpired:
        pytest.fail(
            "exploit_deep.dfi did not terminate; the deep chain must be handled "
            "in bounded time, not looped on without progress."
        )
    _assert_no_crash(r, "exploit_deep.dfi")
    if r.returncode == 0:
        summary = json.loads(r.stdout)
        assert summary.get("data_bytes") == 1, (
            f"exploit_deep.dfi resolved to data_bytes={summary.get('data_bytes')}, "
            f"not the true value 1; a resolver that exits zero must report the "
            f"correct summary"
        )


def test_exploit_cycle_rejected(built):
    """A directory that names itself as a child must be rejected, not resolved
    forever until the stack runs off its end."""
    assert_clean_rejection(parse(EXPLOITS / "exploit_cycle.dfi"), "exploit_cycle.dfi")


def test_exploit_linkwalk_rejected(built):
    """A hardlink edge read past the end of the links table must be rejected."""
    assert_clean_rejection(parse(EXPLOITS / "exploit_linkwalk.dfi"), "exploit_linkwalk.dfi")


def test_exploit_linkidx_rejected(built):
    """A hardlink edge index outside the inode array must be rejected."""
    assert_clean_rejection(parse(EXPLOITS / "exploit_linkidx.dfi"), "exploit_linkidx.dfi")


def test_exploit_xattr_rejected(built):
    """An xattr value length that runs past its region must be rejected."""
    assert_clean_rejection(parse(EXPLOITS / "exploit_xattr.dfi"), "exploit_xattr.dfi")


def test_rejections_name_distinct_subsystems(built):
    """A genuine hardening bounds each field where it is read, so the message it
    prints names the specific subsystem that caught the input, and across the
    whole hostile corpus several different subsystems are named. A blanket
    crash-catcher that funnels every rejection through one generic message cannot
    reproduce that per-path specificity, so the corpus must name several distinct
    subsystems."""
    seen = set()
    for f in sorted(EXPLOITS.glob("exploit_*.dfi")):
        try:
            r = parse(f)
        except subprocess.TimeoutExpired:
            continue
        if r.returncode is None or r.returncode <= 0:
            continue
        err = r.stderr.lower()
        if any(sig in err for sig in CRASH_SIGNATURES):
            continue
        for sub in SUBSYS:
            if f"imgscan: {sub}:" in err:
                seen.add(sub)
    assert len(seen) >= 4, (
        f"only {len(seen)} distinct subsystems were named across the hostile "
        f"corpus ({sorted(seen)}); a real hardening names the specific path that "
        f"caught each input rather than turning every one away with a single "
        f"generic message"
    )


def test_exploit_volfield_rejected(built):
    """A volume descriptor whose fixed-width label offset is read past the end
    of the volumes region must be rejected."""
    assert_clean_rejection(parse(EXPLOITS / "exploit_volfield.dfi"), "exploit_volfield.dfi")


def test_last_index_refs_still_resolve(built):
    """A directory whose child is the last inode, and a hardlink edge on the last
    inode, must still resolve after the bounds checks, not be refused off by
    one."""
    for name in ("valid_006.dfi", "valid_007.dfi"):
        p = VALID / name
        assert p.exists(), f"{name} is missing"
        _check_summary(name, parse(p))


def test_deep_tree_still_parses(built):
    """The deep but legal directory chain must keep parsing after the recursion
    bound. A fix that caps nesting below the corpus depth would wrongly reject
    it."""
    r = parse(VALID / "valid_008.dfi")
    assert r.returncode == 0, (
        f"valid_008.dfi (deep chain) was rejected; the fix is too "
        f"aggressive.\nstderr:\n{r.stderr}"
    )
    summary = json.loads(r.stdout)
    assert summary.get("dir_inodes") == 20 and summary.get("data_bytes") == 2, (
        f"valid_008.dfi dir_inodes={summary.get('dir_inodes')} "
        f"data_bytes={summary.get('data_bytes')} disagree with the known "
        f"values (20, 2)"
    )


def test_boundary_valid_files_still_parse(built):
    """Boundary-packed valid files must still parse despite the bounds checks."""
    for name in ("valid_005.dfi", "valid_009.dfi", "valid_010.dfi"):
        p = VALID / name
        assert p.exists(), f"boundary fixture {name} is missing"
        _check_summary(name, parse(p))


def test_shared_subtree_still_parses(built):
    """The shipped shared-subtree image, whose footprint is amplified by
    multiplicity, must parse to its true total (4096 from thirteen inodes)."""
    _check_summary("valid_011.dfi", parse(VALID / "valid_011.dfi"))


# ---------------------------------------------------------------------------
# Generated-at-test-time fixtures: a valid file the agent has never seen must
# parse, and a freshly minted out-of-bounds file must reject cleanly. This
# guards against a fix that special-cases the shipped corpus byte-for-byte.
# ---------------------------------------------------------------------------
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


def _mint(label_off):
    """Build a one-volume, one-file-inode image whose volume label sits at
    *label_off* in the names pool and whose file carries a single resident
    byte."""
    names = b"gen\x00"
    volumes = _uleb(1) + (_u32(label_off) + b"\x01" + _uleb(64))
    inodes = _uleb(1) + (_u32(7) + b"\x00" + b"\x00" + _uleb(1) + b"\x05")
    links = b""
    xattrs = b""

    regions = {0: names, 1: volumes, 2: inodes, 3: links, 4: xattrs}
    header = b"DFIM" + bytes([2, 5, 0, 0])
    cursor = 8 + 5 * 9
    placed = {}
    body = bytearray()
    for kind in (0, 1, 2, 3, 4):
        placed[kind] = (cursor, len(regions[kind]))
        body += regions[kind]
        cursor += len(regions[kind])
    table = bytearray()
    for kind in (0, 1, 2, 3, 4):
        off, size = placed[kind]
        table += bytes([kind]) + _u32(off) + _u32(size)
    return header + bytes(table) + bytes(body)


def _mint_fanout(depth, k):
    """Build a well-formed image of *depth* directories where each directory
    lists the next one *k* times, ending in a one-byte file. The footprint is
    counted with multiplicity, so it is k**depth even though the image holds only
    depth+1 inodes."""
    names = b"gen\x00"
    volumes = _uleb(1) + (_u32(0) + b"\x01" + _uleb(64))
    inode_blobs = []
    for i in range(depth):
        children = b"".join(_uleb(i + 1) for _ in range(k))
        inode_blobs.append(_u32(i) + b"\x00" + b"\x01" + _uleb(k) + children)
    inode_blobs.append(_u32(depth) + b"\x00" + b"\x00" + _uleb(1) + b"\x00")
    inodes = _uleb(depth + 1) + b"".join(inode_blobs)
    links = b""
    xattrs = b""

    regions = {0: names, 1: volumes, 2: inodes, 3: links, 4: xattrs}
    header = b"DFIM" + bytes([2, 5, 0, 0])
    cursor = 8 + 5 * 9
    placed = {}
    body = bytearray()
    for kind in (0, 1, 2, 3, 4):
        placed[kind] = (cursor, len(regions[kind]))
        body += regions[kind]
        cursor += len(regions[kind])
    table = bytearray()
    for kind in (0, 1, 2, 3, 4):
        off, size = placed[kind]
        table += bytes([kind]) + _u32(off) + _u32(size)
    return header + bytes(table) + bytes(body)


def test_fanout_resolves_in_bounded_time(built, tmp_path):
    """A well-formed image whose directories share subtrees so widely that the
    total resident footprint is enormous must still be summed exactly and in
    bounded time. A resolver that re-walks each shared subtree every time it is
    named does work proportional to the footprint itself and cannot finish;
    settling each inode's footprint once keeps the work proportional to the
    number of inodes. The footprint here is 10**16, well within the 64-bit
    total, from only seventeen inodes."""
    depth, k = 16, 10
    expected = k ** depth
    p = tmp_path / "fanout.dfi"
    p.write_bytes(_mint_fanout(depth, k))
    try:
        r = run([str(BINARY), str(p)], timeout=60)
    except subprocess.TimeoutExpired:
        pytest.fail(
            "the shared-subtree image did not resolve in bounded time; the "
            "resolver re-expands shared subtrees instead of settling each "
            "inode's footprint once"
        )
    assert r.returncode == 0, (
        f"the shared-subtree image was rejected (rc={r.returncode}):\n{r.stderr}"
    )
    summary = json.loads(r.stdout)
    assert summary.get("data_bytes") == expected, (
        f"data_bytes={summary.get('data_bytes')} disagrees with the true "
        f"footprint {expected}"
    )


def test_generated_valid_parses(built, tmp_path):
    """A freshly generated valid file must parse cleanly."""
    p = tmp_path / "gen_valid.dfi"
    p.write_bytes(_mint(0))
    r = parse(p)
    assert r.returncode == 0, f"generated valid file was rejected:\n{r.stderr}"
    summary = json.loads(r.stdout)
    assert summary.get("inodes_defined") == 1
    assert summary.get("data_bytes") == 1


def test_generated_oob_name_rejected(built, tmp_path):
    """A freshly generated file whose volume label offset is far past the names
    pool must reject cleanly, not crash."""
    p = tmp_path / "gen_oob.dfi"
    p.write_bytes(_mint(0x40000000))
    assert_clean_rejection(parse(p), "gen_oob.dfi")


def test_binary_is_native_elf(built):
    """The hardened reader must be a native compiled C executable, not a script or a
    wrapper in another language that only imitates the tool. The binary must
    begin with the ELF magic, so a wrong-language or wrapper bypass of the C
    hardening is rejected before its behaviour is even considered."""
    with open(BINARY, "rb") as fh:
        magic = fh.read(4)
    assert magic == b"\x7fELF", (
        f"the imgscan binary is not a native ELF executable (magic {magic!r}); "
        f"the parser must be compiled C, not a script or a wrapper"
    )


def test_binary_links_electric_fence(built):
    """The rebuilt binary must still link the Electric Fence guard-page
    allocator, so an incomplete fix that reads out of bounds still faults on its
    exploit instead of passing silently. A Makefile edited to drop -lefence would
    weaken the very check that proves each latent weakness is closed."""
    r = run(["ldd", str(BINARY)])
    assert r.returncode == 0, f"could not inspect the binary with ldd:\n{r.stderr}"
    assert "efence" in r.stdout.lower(), (
        "the imgscan binary is not linked against Electric Fence; the guard-page "
        f"allocator that catches an out-of-bounds read is missing.\n{r.stdout}"
    )
