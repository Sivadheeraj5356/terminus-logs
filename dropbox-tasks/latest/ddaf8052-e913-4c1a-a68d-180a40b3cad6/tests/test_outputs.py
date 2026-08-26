"""Behavioral verifier for the Rust quarantine extractor."""

import hashlib
import io
import os
import stat
import struct
import subprocess
import tarfile
import warnings
import zipfile
import zlib
from pathlib import Path

import pytest


APP = Path("/app")
MAX_ENTRY_BYTES = 262_144
SAFE_REPORT = b"incident report\n"
SAFE_RECEIPT = b"quarantine receipt\n"
SAFE_PLAIN = b"not an archive\n"
SAFE_PRIMARY = b"primary record\n"
SAFE_CHAIN = b"nested chain\n"


@pytest.fixture(scope="session")
def extractor_binary():
    """Build the submitted Rust implementation once in offline mode."""
    environment = os.environ.copy()
    environment["CARGO_NET_OFFLINE"] = "true"
    subprocess.run(
        ["cargo", "test", "--locked", "--offline"],
        cwd=APP,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    subprocess.run(
        ["cargo", "build", "--locked", "--offline"],
        cwd=APP,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return APP / "target" / "debug" / "quarantine-extractor"


def _zip_info(name, mode, compression):
    """Create ZIP metadata with an explicit Unix file type and compression."""
    info = zipfile.ZipInfo(name)
    info.create_system = 3
    info.external_attr = mode << 16
    info.compress_type = compression
    return info


def _zip_bytes(entries=(), directories=(), symlinks=()):
    """Build an in-memory ZIP archive with regular entries, dirs, and links."""
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name in directories:
            normalized = name if name.endswith("/") else f"{name}/"
            archive.writestr(
                _zip_info(
                    normalized,
                    stat.S_IFDIR | 0o755,
                    zipfile.ZIP_STORED,
                ),
                b"",
            )
        for record in entries:
            name, data, *options = record
            method = options[0] if options else zipfile.ZIP_DEFLATED
            mode = options[1] if len(options) > 1 else stat.S_IFREG | 0o644
            archive.writestr(
                _zip_info(name, mode, method),
                data,
            )
        for name, target in symlinks:
            archive.writestr(
                _zip_info(
                    name,
                    stat.S_IFLNK | 0o777,
                    zipfile.ZIP_STORED,
                ),
                target.encode(),
            )
    return stream.getvalue()


def _zip_with_local_name_mismatch():
    """Build a ZIP whose local path traverses but central path looks safe."""
    archive = bytearray(
        _zip_bytes(
            entries=[("safe-file.txt", b"reviewed", zipfile.ZIP_STORED)]
        )
    )
    replacement = b"../escape.txt"
    name_size = struct.unpack_from("<H", archive, 26)[0]
    assert name_size == len(replacement)
    archive[30 : 30 + name_size] = replacement
    return bytes(archive)


def _zip_with_unlisted_local_record():
    """Prefix a valid ZIP with a local record absent from its central index."""
    payload = b"hidden"
    name = b"orphan.bin"
    orphan = struct.pack(
        "<IHHHHHIIIHH",
        0x04034B50,
        20,
        0,
        0,
        0,
        0,
        zlib.crc32(payload) & 0xFFFFFFFF,
        len(payload),
        len(payload),
        len(name),
        0,
    ) + name + payload

    archive = bytearray(
        _zip_bytes(
            entries=[("reviewed.txt", b"reviewed", zipfile.ZIP_STORED)]
        )
    )
    end_offset = archive.rfind(b"PK\x05\x06")
    assert end_offset >= 0
    central_offset = struct.unpack_from("<I", archive, end_offset + 16)[0]
    total_entries = struct.unpack_from("<H", archive, end_offset + 10)[0]
    cursor = central_offset
    for _ in range(total_entries):
        assert archive[cursor : cursor + 4] == b"PK\x01\x02"
        local_offset = struct.unpack_from("<I", archive, cursor + 42)[0]
        struct.pack_into(
            "<I",
            archive,
            cursor + 42,
            local_offset + len(orphan),
        )
        name_size, extra_size, comment_size = struct.unpack_from(
            "<HHH",
            archive,
            cursor + 28,
        )
        cursor += 46 + name_size + extra_size + comment_size
    struct.pack_into(
        "<I",
        archive,
        end_offset + 16,
        central_offset + len(orphan),
    )
    return orphan + bytes(archive)


def _zip_with_data_descriptor():
    """Build a safe ZIP whose local sizes are supplied by a data descriptor."""

    class UnseekableBuffer(io.BytesIO):
        def seekable(self):
            return False

        def seek(self, *args, **kwargs):
            raise io.UnsupportedOperation("not seekable")

    stream = UnseekableBuffer()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(
            "descriptor.txt",
            b"descriptor payload",
            compress_type=zipfile.ZIP_DEFLATED,
        )
    return stream.getvalue()


def _tar_bytes(
    files=(),
    directories=(),
    symlinks=(),
    hardlinks=(),
    specials=(),
    *,
    tar_format=tarfile.USTAR_FORMAT,
):
    """Build an in-memory TAR archive with controlled file/link entry types."""
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tar_format) as archive:
        for name in directories:
            info = tarfile.TarInfo(name.rstrip("/") + "/")
            info.type = tarfile.DIRTYPE
            info.mode = 0o755
            archive.addfile(info)
        for record in files:
            name, data, *mode = record
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = mode[0] if mode else 0o644
            archive.addfile(info, io.BytesIO(data))
        for name, target in symlinks:
            info = tarfile.TarInfo(name)
            info.type = tarfile.SYMTYPE
            info.linkname = target
            info.mode = 0o777
            archive.addfile(info)
        for name, target in hardlinks:
            info = tarfile.TarInfo(name)
            info.type = tarfile.LNKTYPE
            info.linkname = target
            archive.addfile(info)
        for name, entry_type in specials:
            info = tarfile.TarInfo(name)
            info.type = entry_type
            info.devmajor = 1
            info.devminor = 3
            archive.addfile(info)
    return stream.getvalue()


def _invoke(binary, directory, archive_bytes, filename="submission.blob"):
    """Run the extractor against archive_bytes and return its result and output."""
    directory.mkdir(parents=True)
    archive_path = directory / filename
    destination = directory / "published"
    archive_path.write_bytes(archive_bytes)
    completed = subprocess.run(
        [str(binary), str(archive_path), str(destination)],
        cwd=APP,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed, destination


def _assert_rejected(completed, destination):
    """Verify a rejected submission left no destination or staging directory."""
    assert completed.returncode != 0
    assert not destination.exists()
    staging = list(
        destination.parent.glob(f".{destination.name}.quarantine-*")
    )
    assert not staging


def _assert_bytes(path, expected):
    """Verify a published regular file has the expected bytes."""
    assert path.is_file()
    assert path.read_bytes() == expected


def _deterministic_noise(size):
    """Return deterministic pseudo-random bytes for incompressible limit tests."""
    chunks = []
    counter = 0
    remaining = size
    while remaining:
        block = hashlib.sha256(counter.to_bytes(8, "big")).digest()
        chunks.append(block[:remaining])
        remaining -= min(remaining, len(block))
        counter += 1
    return b"".join(chunks)


def _nested_zip(boundaries):
    """Build ZIP-in-ZIP data with the requested number of archive boundaries."""
    payload = _zip_bytes(entries=[("leaf.txt", b"leaf\n")])
    for level in range(boundaries):
        payload = _zip_bytes(
            entries=[
                (
                    f"level-{level}.bin",
                    payload,
                    zipfile.ZIP_STORED,
                )
            ]
        )
    return payload


def test_documented_safe_tar_zip_nesting_and_links(extractor_binary, tmp_path):
    """Preserve safe files, modes, links, Unicode names, and nested formats."""
    nested_zip = _zip_bytes(
        entries=[("nested/receipt.txt", SAFE_RECEIPT)]
    )
    safe_tar = _tar_bytes(
        directories=["docs"],
        files=[
            ("docs/report.txt", SAFE_REPORT),
            ("docs/run-review.sh", b"#!/bin/sh\nexit 0\n", 0o755),
            ("evidence.bin", nested_zip),
            ("looks.zip", SAFE_PLAIN),
            ("Résumé.txt", b"reviewed\n"),
        ],
        symlinks=[("docs/latest.txt", "report.txt")],
        hardlinks=[("copies/report.txt", "docs/report.txt")],
    )
    completed, destination = _invoke(
        extractor_binary,
        tmp_path / "safe-tar",
        safe_tar,
    )
    assert completed.returncode == 0
    _assert_bytes(destination / "docs/report.txt", SAFE_REPORT)
    _assert_bytes(
        destination / "evidence.bin/nested/receipt.txt",
        SAFE_RECEIPT,
    )
    _assert_bytes(destination / "looks.zip", SAFE_PLAIN)
    assert (destination / "docs/latest.txt").is_symlink()
    assert os.readlink(destination / "docs/latest.txt") == "report.txt"
    assert (
        os.stat(destination / "docs/report.txt").st_ino
        == os.stat(destination / "copies/report.txt").st_ino
    )
    assert stat.S_IMODE(
        os.stat(destination / "docs/run-review.sh").st_mode
    ) == 0o755
    assert stat.S_IMODE(
        os.stat(destination / "docs/report.txt").st_mode
    ) == 0o644

    nested_tar = _tar_bytes(files=[("chain.txt", SAFE_CHAIN)])
    safe_zip = _zip_bytes(
        directories=["records"],
        entries=[
            ("records/primary.txt", SAFE_PRIMARY),
            (
                "records/run-verify.sh",
                b"#!/bin/sh\nexit 0\n",
                zipfile.ZIP_STORED,
                stat.S_IFREG | 0o755,
            ),
            ("nested/payload.dat", nested_tar, zipfile.ZIP_STORED),
        ],
        symlinks=[("records/alias.txt", "primary.txt")],
    )
    completed, destination = _invoke(
        extractor_binary,
        tmp_path / "safe-zip",
        safe_zip,
    )
    assert completed.returncode == 0
    _assert_bytes(destination / "records/primary.txt", SAFE_PRIMARY)
    assert stat.S_IMODE(
        os.stat(destination / "records/run-verify.sh").st_mode
    ) == 0o755
    _assert_bytes(destination / "records/alias.txt", SAFE_PRIMARY)
    _assert_bytes(destination / "nested/payload.dat/chain.txt", SAFE_CHAIN)


def test_traversal_prefixes_and_late_failure_are_atomic(
    extractor_binary,
    tmp_path,
):
    """Reject slash, backslash, drive, and parent traversal without partial output."""
    attacks = [
        _zip_bytes(entries=[("../sentinel.txt", b"changed")]),
        _zip_bytes(entries=[("/tmp/archive-absolute.txt", b"changed")]),
        _zip_bytes(entries=[("C:/archive-drive.txt", b"changed")]),
        _zip_bytes(entries=[("safe\\..\\sentinel.txt", b"changed")]),
        _tar_bytes(files=[("../sentinel.txt", b"changed")]),
        _zip_bytes(
            entries=[
                ("first-safe.txt", b"must not publish"),
                ("../sentinel.txt", b"changed"),
            ]
        ),
    ]
    for index, attack in enumerate(attacks):
        case = tmp_path / f"traversal-{index}"
        case.mkdir()
        sentinel = case / "sentinel.txt"
        sentinel.write_bytes(b"unchanged")
        completed, destination = _invoke(
            extractor_binary,
            case / "request",
            attack,
        )
        _assert_rejected(completed, destination)
        assert sentinel.read_bytes() == b"unchanged"


def test_symlink_hardlink_and_link_chain_escapes(extractor_binary, tmp_path):
    """Reject escaping, dangling, and chained links while publishing no artifacts."""
    attacks = [
        _tar_bytes(
            files=[("safe.txt", b"safe")],
            symlinks=[("escape", "../../outside.txt")],
        ),
        _tar_bytes(
            files=[("safe.txt", b"safe")],
            hardlinks=[("escape", "../outside.txt")],
        ),
        _tar_bytes(
            files=[("safe.txt", b"safe")],
            symlinks=[("first", "safe.txt"), ("second", "first")],
        ),
        _tar_bytes(symlinks=[("dangling", "missing.txt")]),
        _zip_bytes(symlinks=[("escape", "../../outside.txt")]),
    ]
    for index, attack in enumerate(attacks):
        completed, destination = _invoke(
            extractor_binary,
            tmp_path / f"link-{index}",
            attack,
        )
        _assert_rejected(completed, destination)


def test_devices_fifos_and_sparse_tar_metadata(extractor_binary, tmp_path):
    """Reject every special node plus GNU and PAX sparse declarations."""
    special_types = [
        tarfile.CHRTYPE,
        tarfile.BLKTYPE,
        tarfile.FIFOTYPE,
        tarfile.GNUTYPE_SPARSE,
    ]
    attacks = [
        _tar_bytes(specials=[("special-node", entry_type)])
        for entry_type in special_types
    ]

    sparse_stream = io.BytesIO()
    with tarfile.open(
        fileobj=sparse_stream,
        mode="w",
        format=tarfile.PAX_FORMAT,
    ) as archive:
        info = tarfile.TarInfo("pax-sparse.bin")
        info.size = 1
        info.pax_headers = {
            "GNU.sparse.map": "0,1",
            "GNU.sparse.size": "10485760",
        }
        archive.addfile(info, io.BytesIO(b"x"))
    attacks.append(sparse_stream.getvalue())

    for index, attack in enumerate(attacks):
        completed, destination = _invoke(
            extractor_binary,
            tmp_path / f"special-{index}",
            attack,
        )
        _assert_rejected(completed, destination)


def test_entry_size_ratio_total_and_count_limits(extractor_binary, tmp_path):
    """Enforce single-entry, compression-ratio, aggregate-byte, and count budgets."""
    attacks = [
        _zip_bytes(
            entries=[
                (
                    "oversized.bin",
                    _deterministic_noise(MAX_ENTRY_BYTES + 1),
                    zipfile.ZIP_STORED,
                )
            ]
        ),
        _zip_bytes(entries=[("ratio.txt", b"A" * 100_000)]),
        _zip_bytes(
            entries=[
                (
                    f"part-{index}.bin",
                    _deterministic_noise(220_000),
                    zipfile.ZIP_STORED,
                )
                for index in range(5)
            ]
        ),
        _zip_bytes(
            entries=[
                (f"entry-{index:02}.txt", b"", zipfile.ZIP_STORED)
                for index in range(65)
            ]
        ),
    ]
    for index, attack in enumerate(attacks):
        completed, destination = _invoke(
            extractor_binary,
            tmp_path / f"limit-{index}",
            attack,
        )
        _assert_rejected(completed, destination)


def test_nested_depth_boundary_and_content_detection(extractor_binary, tmp_path):
    """Accept three nested boundaries, reject four, and distrust malformed magic."""
    accepted, destination = _invoke(
        extractor_binary,
        tmp_path / "depth-three",
        _nested_zip(3),
    )
    assert accepted.returncode == 0
    leaves = list(destination.rglob("leaf.txt"))
    assert len(leaves) == 1
    _assert_bytes(leaves[0], b"leaf\n")

    rejected, destination = _invoke(
        extractor_binary,
        tmp_path / "depth-four",
        _nested_zip(4),
    )
    _assert_rejected(rejected, destination)

    malformed_nested = _zip_bytes(
        entries=[
            ("nested.bin", b"PK\x03\x04truncated", zipfile.ZIP_STORED)
        ]
    )
    rejected, destination = _invoke(
        extractor_binary,
        tmp_path / "malformed-nested",
        malformed_nested,
    )
    _assert_rejected(rejected, destination)


def test_zip_header_reconciliation_and_unlisted_records(
    extractor_binary,
    tmp_path,
):
    """Reject ZIP parser differentials hidden outside the central index."""
    attacks = [
        _zip_with_local_name_mismatch(),
        _zip_with_unlisted_local_record(),
    ]
    for index, attack in enumerate(attacks):
        completed, destination = _invoke(
            extractor_binary,
            tmp_path / f"zip-envelope-{index}",
            attack,
        )
        _assert_rejected(completed, destination)

    completed, destination = _invoke(
        extractor_binary,
        tmp_path / "zip-descriptor",
        _zip_with_data_descriptor(),
    )
    assert completed.returncode == 0
    _assert_bytes(destination / "descriptor.txt", b"descriptor payload")


def test_tar_end_marker_rejects_concatenated_payload(
    extractor_binary,
    tmp_path,
):
    """Reject a second TAR hidden after the first archive's end marker."""
    visible = _tar_bytes(files=[("reviewed.txt", b"reviewed")])
    hidden = _tar_bytes(files=[("../escape.txt", b"changed")])
    completed, destination = _invoke(
        extractor_binary,
        tmp_path / "tar-envelope",
        visible + hidden,
    )
    _assert_rejected(completed, destination)


def test_unicode_duplicate_and_prefix_collisions(extractor_binary, tmp_path):
    """Reject NFKC, case, duplicate, and file/directory identity collisions."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        attacks = [
            _zip_bytes(
                entries=[
                    ("café.txt", b"one"),
                    ("cafe\u0301.txt", b"two"),
                ]
            ),
            _zip_bytes(
                entries=[("Admin.txt", b"one"), ("admin.txt", b"two")]
            ),
            _zip_bytes(
                entries=[("Key.txt", b"one"), ("key.txt", b"two")]
            ),
            _zip_bytes(
                entries=[("duplicate.txt", b"one"), ("duplicate.txt", b"two")]
            ),
            _zip_bytes(
                entries=[("node", b"file"), ("node/child.txt", b"child")]
            ),
        ]
    for index, attack in enumerate(attacks):
        completed, destination = _invoke(
            extractor_binary,
            tmp_path / f"collision-{index}",
            attack,
        )
        _assert_rejected(completed, destination)


def test_host_path_preconditions_and_unrecognized_root(extractor_binary, tmp_path):
    """Reject input symlinks, existing outputs, symlinked parents, and unknown roots."""
    unknown, destination = _invoke(
        extractor_binary,
        tmp_path / "unknown-root",
        b"this is not an archive",
        filename="misleading.zip",
    )
    _assert_rejected(unknown, destination)

    case = tmp_path / "input-symlink"
    case.mkdir()
    real_input = case / "real.tar"
    real_input.write_bytes(_tar_bytes(files=[("safe.txt", b"safe")]))
    linked_input = case / "linked.tar"
    linked_input.symlink_to(real_input)
    destination = case / "published"
    completed = subprocess.run(
        [str(extractor_binary), str(linked_input), str(destination)],
        cwd=APP,
        capture_output=True,
        text=True,
        timeout=30,
    )
    _assert_rejected(completed, destination)

    case = tmp_path / "existing-output"
    case.mkdir()
    archive_path = case / "safe.tar"
    archive_path.write_bytes(_tar_bytes(files=[("safe.txt", b"safe")]))
    destination = case / "published"
    destination.mkdir()
    marker = destination / "marker.txt"
    marker.write_bytes(b"keep")
    completed = subprocess.run(
        [str(extractor_binary), str(archive_path), str(destination)],
        cwd=APP,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode != 0
    assert marker.read_bytes() == b"keep"

    case = tmp_path / "symlink-parent"
    case.mkdir()
    real_parent = case / "real-parent"
    real_parent.mkdir()
    linked_parent = case / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    archive_path = case / "safe.tar"
    archive_path.write_bytes(_tar_bytes(files=[("safe.txt", b"safe")]))
    destination = linked_parent / "published"
    completed = subprocess.run(
        [str(extractor_binary), str(archive_path), str(destination)],
        cwd=APP,
        capture_output=True,
        text=True,
        timeout=30,
    )
    _assert_rejected(completed, destination)
