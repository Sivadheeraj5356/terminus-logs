# ruff: noqa: E501
"""Reference oracle for CDC vault v3."""
from __future__ import annotations

import gzip
import hashlib
import hmac
import io
import json
import os
import stat
import struct
import tarfile
from pathlib import Path
from typing import Any

ZERO64 = "0" * 64
MIN_CHUNK = 3072
MAX_CHUNK = 12288
MASK = 0x1FFF


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha512_256_hex(data: bytes) -> str:
    return hashlib.new("sha512_256", data).hexdigest()


def u32be(n: int) -> bytes:
    return struct.pack(">I", n & 0xFFFFFFFF)


def dumps(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def derive_policy(body: bytes) -> dict[str, Any]:
    body_hash = sha256(body)
    gear_seed = sha256(b"gear\0" + body)
    mac_key = sha256(b"hmac\0" + body)
    store_salt = sha256(b"store\0" + body)
    return {
        "sha256": body_hash.hex(),
        "byte_length": len(body),
        "attestation_domain": body_hash.hex()[:32],
        "gear_seed": gear_seed,
        "gear_seed_hex": gear_seed.hex(),
        "store_salt": store_salt,
        "store_salt_hex": store_salt.hex(),
        "mac_key": mac_key,
        "mac_key_hex": mac_key.hex(),
    }


def build_gear(gear_seed: bytes) -> list[int]:
    table = []
    for i in range(256):
        digest = sha256(gear_seed + u32be(i))
        table.append(struct.unpack(">I", digest[:4])[0])
    return table


def cdc_chunk(data: bytes, gear: list[int]) -> list[bytes]:
    if not data:
        return []
    chunks: list[bytes] = []
    start = 0
    fp = 0
    length = 0
    for i, b in enumerate(data):
        fp = ((fp << 1) + gear[b]) & 0xFFFFFFFF
        length += 1
        cut = length >= MAX_CHUNK or (length >= MIN_CHUNK and (fp & MASK) == 0)
        if cut:
            chunks.append(data[start : i + 1])
            start = i + 1
            fp = 0
            length = 0
    if start < len(data):
        chunks.append(data[start:])
    return chunks


def find_holes(data: bytes) -> list[dict[str, int]]:
    holes = []
    i = 0
    n = len(data)
    while i < n:
        if data[i] != 0:
            i += 1
            continue
        j = i
        while j < n and data[j] == 0:
            j += 1
        if j - i >= 2048:
            holes.append({"offset": i, "length": j - i})
        i = j
    return holes


def merkle_root(chunk_ids: list[str]) -> str:
    uniq = sorted(set(chunk_ids))
    if not uniq:
        return ZERO64
    level = [sha256(bytes([0xA5]) + cid.encode("ascii")) for cid in uniq]
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            if i + 1 == len(level):
                nxt.append(level[i])
            else:
                nxt.append(sha256(bytes([0x5A]) + level[i] + level[i + 1]))
        level = nxt
    return level[0].hex()


def path_excluded(rel: str, patterns: list[str]) -> bool:
    import fnmatch

    base = rel.rsplit("/", 1)[-1]
    for pat in patterns:
        if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(base, pat):
            return True
    return False


def scan_job(src: Path, exclude: list[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    inode_first: dict[tuple[int, int], str] = {}
    for dirpath, dirnames, filenames in os.walk(src, followlinks=False):
        dirnames.sort()
        filenames.sort()
        for name in sorted(dirnames + filenames):
            full = Path(dirpath) / name
            rel = full.relative_to(src).as_posix()
            if path_excluded(rel, exclude):
                continue
            st = full.lstat()
            if stat.S_ISLNK(st.st_mode):
                entries.append(
                    {
                        "path": rel,
                        "kind": "symlink",
                        "size": 0,
                        "target": os.readlink(full),
                        "dev": st.st_dev,
                        "ino": st.st_ino,
                        "mode": st.st_mode,
                    }
                )
            elif stat.S_ISREG(st.st_mode):
                key = (st.st_dev, st.st_ino)
                if key in inode_first:
                    entries.append(
                        {
                            "path": rel,
                            "kind": "hardlink",
                            "size": st.st_size,
                            "primary_path": inode_first[key],
                            "dev": st.st_dev,
                            "ino": st.st_ino,
                            "mode": st.st_mode,
                        }
                    )
                else:
                    inode_first[key] = rel
                    entries.append(
                        {
                            "path": rel,
                            "kind": "regular",
                            "size": st.st_size,
                            "dev": st.st_dev,
                            "ino": st.st_ino,
                            "mode": st.st_mode,
                            "full": full,
                        }
                    )
    # fix hardlink primaries to shallowest-then-lex among group
    groups: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for e in entries:
        if e["kind"] in ("regular", "hardlink"):
            groups.setdefault((e["dev"], e["ino"]), []).append(e)
    for members in groups.values():
        def depth(p: str) -> int:
            return p.count("/")

        primary = sorted(members, key=lambda m: (depth(m["path"]), m["path"]))[0]
        for m in members:
            if m is primary:
                m["kind"] = "regular"
                m.pop("primary_path", None)
                if "full" not in m:
                    m["full"] = src / m["path"]
            else:
                m["kind"] = "hardlink"
                m["primary_path"] = primary["path"]
                m.pop("full", None)
    entries.sort(key=lambda e: e["path"])
    return entries


def process_batch(
    data_root: Path,
    output: Path,
    policy_body: bytes,
    policy_url: str,
) -> dict[str, Any]:
    policy = derive_policy(policy_body)
    gear = build_gear(policy["gear_seed"])
    store_salt: bytes = policy["store_salt"]

    output.mkdir(parents=True, exist_ok=True)
    chunk_store = output / "chunk_store"
    chunk_store.mkdir(exist_ok=True)

    receipt = {
        "url": policy_url,
        "sha256": policy["sha256"],
        "byte_length": policy["byte_length"],
        "attestation_domain": policy["attestation_domain"],
        "gear_seed_hex": policy["gear_seed_hex"],
        "store_salt_hex": policy["store_salt_hex"],
        "mac_key_hex": policy["mac_key_hex"],
    }
    (output / "policy_receipt.json").write_text(dumps(receipt), encoding="utf-8")

    manifest = json.loads((data_root / "manifest.json").read_text(encoding="utf-8"))
    job_list: list[tuple[str, Path, Path]] = []
    for job in manifest["jobs"]:
        job_list.append(
            (
                job["id"],
                data_root / job["src"],
                data_root / job["config"],
            )
        )
    remote_root = Path("/app/resources/remote_catalog")
    extra = remote_root / "extra_jobs.json"
    if extra.is_file():
        for job in json.loads(extra.read_text(encoding="utf-8")):
            job_list.append(
                (
                    job["id"],
                    remote_root / job["src"],
                    remote_root / job["config"],
                )
            )

    global_chunks: dict[str, dict[str, Any]] = {}
    written_stores: set[str] = set()
    file_primary: dict[str, tuple[str, str]] = {}  # file_id -> (job_id, path)
    report_rows: list[dict[str, Any]] = []
    ledger_entries: list[dict[str, Any]] = []
    prev_hash = ZERO64

    for job_id, src, cfg_path in job_list:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        exclude = list(cfg.get("exclude") or [])
        gzip_level = int(cfg["gzip_level"])
        scanned = scan_job(src, exclude)
        if any("__deny__" in e["path"] for e in scanned):
            report_rows.append(
                {
                    "job_id": job_id,
                    "status": "quarantined",
                    "file_count": None,
                    "byte_count": None,
                    "chunk_count": None,
                    "unique_chunks": None,
                    "merkle_root": None,
                }
            )
            continue
        if not scanned:
            report_rows.append(
                {
                    "job_id": job_id,
                    "status": "failed",
                    "file_count": None,
                    "byte_count": None,
                    "chunk_count": None,
                    "unique_chunks": None,
                    "merkle_root": None,
                }
            )
            continue

        job_out = output / "jobs" / job_id
        job_out.mkdir(parents=True, exist_ok=True)
        catalog: dict[str, dict[str, Any]] = {}
        manifest_files = []
        restore_entries = []
        primary_by_path: dict[str, dict[str, Any]] = {}
        stored_bytes = 0
        total_bytes = 0
        alias_files = 0
        primary_files = 0
        all_chunk_slots = 0

        # first pass: load primary bodies
        body_cache: dict[str, bytes] = {}
        for e in scanned:
            if e["kind"] == "regular":
                body = Path(e["full"]).read_bytes()
                body_cache[e["path"]] = body
                e["body"] = body
                e["file_id"] = sha512_256_hex(body)
                e["holes"] = find_holes(body)
                chunks = cdc_chunk(body, gear)
                e["chunk_ids"] = []
                e["store_names"] = []
                for ch in chunks:
                    cid = sha512_256_hex(ch)
                    sname = sha256_hex(store_salt + ch)
                    e["chunk_ids"].append(cid)
                    e["store_names"].append(sname)
                    if cid not in catalog:
                        catalog[cid] = {
                            "chunk_id": cid,
                            "store_name": sname,
                            "size": len(ch),
                            "ref_count": 0,
                            "bytes": ch,
                        }
                primary_by_path[e["path"]] = e

        for e in scanned:
            if e["kind"] == "hardlink":
                prim = primary_by_path[e["primary_path"]]
                e["file_id"] = prim["file_id"]
                e["chunk_ids"] = list(prim["chunk_ids"])
                e["store_names"] = list(prim["store_names"])
                e["holes"] = []
                e["body"] = None

        for e in scanned:
            if e["kind"] == "symlink":
                manifest_files.append(
                    {
                        "path": e["path"],
                        "kind": "symlink",
                        "size": 0,
                        "file_id": None,
                        "chunk_ids": [],
                        "link_target": e["target"],
                        "primary_path": None,
                    }
                )
                restore_entries.append(
                    {
                        "path": e["path"],
                        "kind": "symlink",
                        "file_id": None,
                        "chunk_ids": [],
                        "holes": [],
                        "primary_path": None,
                    }
                )
                continue

            fid = e["file_id"]
            is_alias = e["kind"] == "hardlink"
            if not is_alias:
                if fid not in file_primary:
                    file_primary[fid] = (job_id, e["path"])
                elif file_primary[fid][0] != job_id or file_primary[fid][1] != e["path"]:
                    # duplicate file content within or across jobs — still primary path for this node
                    pass
                primary_files += 1
                total_bytes += e["size"]
            else:
                alias_files += 1
                total_bytes += e["size"]

            for cid in e["chunk_ids"]:
                catalog[cid]["ref_count"] += 1
                all_chunk_slots += 1
                if cid not in global_chunks:
                    global_chunks[cid] = {
                        "chunk_id": cid,
                        "store_name": catalog[cid]["store_name"],
                        "size": catalog[cid]["size"],
                        "ref_count": 0,
                    }
                global_chunks[cid]["ref_count"] += 1

            # write store objects for this job's chunks (first write wins)
            if e["kind"] == "regular":
                for cid, sname, ch in zip(
                    e["chunk_ids"], e["store_names"], cdc_chunk(e["body"], gear)
                ):
                    if sname not in written_stores:
                        dest = chunk_store / sname[:2] / sname
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(ch)
                        written_stores.add(sname)
                        stored_bytes += len(ch)

            manifest_files.append(
                {
                    "path": e["path"],
                    "kind": e["kind"],
                    "size": e["size"],
                    "file_id": e["file_id"],
                    "chunk_ids": e["chunk_ids"],
                    "link_target": None,
                    "primary_path": e.get("primary_path"),
                }
            )
            restore_entries.append(
                {
                    "path": e["path"],
                    "kind": e["kind"],
                    "file_id": e["file_id"],
                    "chunk_ids": e["chunk_ids"],
                    "holes": e.get("holes") or [],
                    "primary_path": e.get("primary_path"),
                }
            )

        chunk_ids_sorted = sorted(catalog.keys())
        root = merkle_root(chunk_ids_sorted)
        store_names_sorted = sorted({catalog[c]["store_name"] for c in chunk_ids_sorted})
        store_binding = sha256_hex("\n".join(store_names_sorted).encode("ascii"))

        man_obj = {"job_id": job_id, "files": manifest_files}
        man_text = dumps(man_obj)
        man_path = job_out / "manifest.json"
        man_path.write_text(man_text, encoding="utf-8")
        man_sha = sha256_hex(man_text.encode("utf-8"))

        cat_obj = {
            "chunks": [
                {
                    "chunk_id": catalog[c]["chunk_id"],
                    "store_name": catalog[c]["store_name"],
                    "size": catalog[c]["size"],
                    "ref_count": catalog[c]["ref_count"],
                }
                for c in chunk_ids_sorted
            ]
        }
        (job_out / "chunk_catalog.json").write_text(dumps(cat_obj), encoding="utf-8")
        (job_out / "dedup_report.json").write_text(
            dumps(
                {
                    "job_id": job_id,
                    "total_files": len(scanned),
                    "primary_files": primary_files,
                    "alias_files": alias_files,
                    "total_bytes": total_bytes,
                    "stored_bytes": stored_bytes,
                }
            ),
            encoding="utf-8",
        )
        (job_out / "restoration_map.json").write_text(
            dumps({"job_id": job_id, "entries": restore_entries}),
            encoding="utf-8",
        )
        (job_out / "summary.json").write_text(
            dumps(
                {
                    "job_id": job_id,
                    "file_count": len(scanned),
                    "byte_count": total_bytes,
                    "chunk_count": all_chunk_slots,
                    "unique_chunks": len(catalog),
                    "merkle_root": root,
                    "gzip_level": gzip_level,
                }
            ),
            encoding="utf-8",
        )

        # tar.gz
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=gzip_level, mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w") as tar:
                for e in scanned:
                    info = tarfile.TarInfo(name=e["path"])
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mtime = 0
                    info.mode = stat.S_IMODE(e["mode"])
                    if e["kind"] == "symlink":
                        info.type = tarfile.SYMTYPE
                        info.linkname = e["target"]
                        info.size = 0
                        tar.addfile(info)
                    elif e["kind"] == "hardlink":
                        info.type = tarfile.LNKTYPE
                        info.linkname = e["primary_path"]
                        info.size = 0
                        tar.addfile(info)
                    else:
                        info.type = tarfile.REGTYPE
                        body = e["body"]
                        info.size = len(body)
                        tar.addfile(info, io.BytesIO(body))
        (job_out / "archive.tar.gz").write_bytes(buf.getvalue())

        msg = "\n".join(
            [
                policy["attestation_domain"],
                job_id,
                root,
                man_sha,
                store_binding,
            ]
        ).encode("utf-8")
        sig = hmac.new(policy["mac_key"], msg, hashlib.sha256).hexdigest()
        (job_out / "attestation.json").write_text(
            dumps(
                {
                    "job_id": job_id,
                    "merkle_root": root,
                    "domain": policy["attestation_domain"],
                    "manifest_sha256": man_sha,
                    "store_binding": store_binding,
                    "signature_hex": sig,
                }
            ),
            encoding="utf-8",
        )

        entry_hash = sha256_hex(
            (prev_hash + job_id + root + store_binding).encode("ascii")
        )
        ledger_entries.append(
            {
                "job_id": job_id,
                "merkle_root": root,
                "store_binding": store_binding,
                "prev_hash": prev_hash,
                "entry_hash": entry_hash,
            }
        )
        prev_hash = entry_hash

        report_rows.append(
            {
                "job_id": job_id,
                "status": "ok",
                "file_count": len(scanned),
                "byte_count": total_bytes,
                "chunk_count": all_chunk_slots,
                "unique_chunks": len(catalog),
                "merkle_root": root,
            }
        )

    (output / "global_chunk_registry.json").write_text(
        dumps(
            {
                "chunks": [
                    global_chunks[c]
                    for c in sorted(global_chunks.keys())
                ]
            }
        ),
        encoding="utf-8",
    )
    (output / "ledger.json").write_text(
        dumps({"entries": ledger_entries}), encoding="utf-8"
    )
    with (output / "report.jsonl").open("w", encoding="utf-8") as fh:
        for row in report_rows:
            fh.write(json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n")

    return {"receipt": receipt, "rows": report_rows, "ledger": ledger_entries}
