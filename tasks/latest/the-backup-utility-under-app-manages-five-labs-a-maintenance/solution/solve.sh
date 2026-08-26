#!/bin/bash
set -euo pipefail

export RUSTUP_HOME="${RUSTUP_HOME:-/usr/local/rustup}"
export CARGO_HOME="${CARGO_HOME:-/usr/local/cargo}"
export PATH="${CARGO_HOME}/bin:${RUSTUP_HOME}/bin:${PATH:-/usr/bin:/bin}"
CARGO="${CARGO:-${CARGO_HOME}/bin/cargo}"
if [[ ! -x "$CARGO" ]]; then
  CARGO="$(command -v cargo)"
fi
export CARGO_NET_OFFLINE="${CARGO_NET_OFFLINE:-true}"

cat > /app/_diagctl.py <<'PYEOF'
#!/usr/bin/env python3
"""Diagnose and repair corrupted backup-system operational state.

The maintenance window on 2026-06-17 introduced six independent
corruption vectors across the five labs.  This script identifies
each vector from the file-system and profile state, applies the
minimal correction, and verifies the fix before proceeding.
"""
import os
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

LABS = Path("/app/labs")
PROFILES = Path("/app/profiles")
LAB_NAMES = ["atlas", "beacon", "cinder", "mesa", "ridge"]


def log(msg: str) -> None:
    print(f"[repair] {msg}", file=sys.stderr)


# ====================================================================
# Phase 1: File-system layout recovery
# Pool files must reside under <lab>/objects/ for the scan path to
# find them.  Two labs were affected by the maintenance window.
# ====================================================================

def recover_pool_directory(lab: str) -> None:
    """If objects/ is missing, find a renamed directory containing blobs."""
    lab_dir = LABS / lab
    objects = lab_dir / "objects"
    if objects.is_dir() and any(objects.glob("*.blob")):
        return
    for child in sorted(lab_dir.iterdir()):
        if not child.is_dir():
            continue
        if child.name in ("recipes", "index", "journal", "ledger", "objects"):
            continue
        blobs = list(child.glob("*.blob"))
        if blobs:
            if objects.is_dir():
                for blob in blobs:
                    dest = objects / blob.name
                    if not dest.exists():
                        shutil.move(str(blob), str(dest))
                        log(f"{lab}: moved {blob.name} from {child.name}/ to objects/")
                if not any(child.iterdir()):
                    child.rmdir()
            else:
                shutil.move(str(child), str(objects))
                log(f"{lab}: renamed {child.name}/ -> objects/")
            return


def recover_misplaced_pools(lab: str) -> None:
    """Move pool files found outside objects/ back into it."""
    lab_dir = LABS / lab
    objects = lab_dir / "objects"
    if not objects.is_dir():
        return
    for child in sorted(lab_dir.iterdir()):
        if child.is_dir() and child != objects:
            for blob in child.glob("*.blob"):
                dest = objects / blob.name
                if not dest.exists():
                    shutil.move(str(blob), str(dest))
                    log(f"{lab}: relocated {blob.name} from {child.name}/ to objects/")
            if child.is_dir() and not any(child.iterdir()):
                child.rmdir()


# ====================================================================
# Phase 2: Profile mask-key recovery
# Determine correct XOR mask keys by comparing raw pool bytes with
# known plaintext from recipe marks.
# ====================================================================

def read_profile(lab: str) -> dict[str, str]:
    """Read the profile for a lab, returning {key: value}."""
    for path in sorted(PROFILES.glob("*.conf")):
        fields: dict[str, str] = {}
        for line in path.read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                fields[k.strip()] = v.strip()
        if fields.get("name") == lab:
            return fields
    return {}


def profile_path(lab: str) -> Path | None:
    """Return path to the profile file for a lab."""
    for path in sorted(PROFILES.glob("*.conf")):
        for line in path.read_text().splitlines():
            if line.strip().startswith("name=") and line.split("=", 1)[1].strip() == lab:
                return path
    return None


def recover_mesa_mask_key() -> None:
    """Determine mesa's correct mask_key by XOR-ing a known pool byte
    against expected plaintext.  m01 starts at pool-a.blob offset 2
    and its first byte is 'm' (0x6d)."""
    pool_a = LABS / "mesa" / "objects" / "pool-a.blob"
    prof = profile_path("mesa")
    if not pool_a.is_file() or prof is None:
        return
    raw = pool_a.read_bytes()
    if len(raw) < 3:
        return
    masked_byte = raw[2]
    correct_key = masked_byte ^ 0x6D  # 'm'
    text = prof.read_text()
    m = re.search(r"^mask_key=(\d+)", text, re.MULTILINE)
    if m and int(m.group(1)) != correct_key:
        new_text = re.sub(r"^mask_key=\d+", f"mask_key={correct_key}", text, flags=re.MULTILINE)
        prof.write_text(new_text)
        log(f"mesa: corrected mask_key from {m.group(1)} to {correct_key}")


def remove_spurious_masking() -> None:
    """Remove mask config from labs whose pool data is plaintext.
    If the raw byte at a known offset already matches expected
    plaintext without XOR, the masking is spurious."""
    for lab in LAB_NAMES:
        if lab == "mesa":
            continue
        prof = profile_path(lab)
        if prof is None:
            continue
        text = prof.read_text()
        if "mask_key=" not in text:
            continue
        m_key = re.search(r"^mask_key=(\d+)", text, re.MULTILINE)
        m_pools = re.search(r"^masked_pools=(.+)", text, re.MULTILINE)
        if not m_key or not m_pools:
            continue
        pool_list = [p.strip() for p in m_pools.group(1).split(",") if p.strip()]
        objects = LABS / lab / "objects"
        plaintext_match = True
        for pool_name in pool_list:
            pool_path = objects / pool_name
            stem = pool_name.removesuffix(".blob")
            if not pool_path.is_file():
                pool_path = objects / f"{stem}.blob"
            if not pool_path.is_file():
                continue
            data = pool_path.read_bytes()
            if len(data) > 4:
                # If all sample bytes are valid ASCII, data is likely plaintext
                sample = data[:min(20, len(data))]
                if all(0x09 <= b <= 0x7E for b in sample):
                    continue
                else:
                    plaintext_match = False
        if plaintext_match:
            new_text = re.sub(r"^mask_key=\d+\n?", "", text, flags=re.MULTILINE)
            new_text = re.sub(r"^masked_pools=.+\n?", "", new_text, flags=re.MULTILINE)
            prof.write_text(new_text)
            log(f"{lab}: removed spurious masking (pool data is plaintext)")


# ====================================================================
# Phase 3: Cross-lab reference recovery
# Borrow lists and scan-order profiles must reference the correct
# supplier lab for cross-lab span recovery.
# ====================================================================

def read_index(lab: str) -> dict[str, tuple[str, int, int]]:
    """Return {span_id: (object, offset, length)} from chunks.idx."""
    idx_path = LABS / lab / "index" / "chunks.idx"
    entries: dict[str, tuple[str, int, int]] = {}
    if not idx_path.is_file():
        return entries
    for line in idx_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) == 4:
            entries[parts[0].strip()] = (parts[1].strip(), int(parts[2]), int(parts[3]))
    return entries


def find_span_supplier(span_id: str, home_lab: str) -> str | None:
    """Find which lab's index references a span (excluding home)."""
    for lab in LAB_NAMES:
        if lab == home_lab:
            continue
        idx = read_index(lab)
        if span_id in idx:
            obj, off, length = idx[span_id]
            pool_path = LABS / lab / "objects" / obj
            if pool_path.is_file():
                return lab
    return None


def recover_ridge_borrow() -> None:
    """Ridge borrows r04 from another lab.  Find the correct supplier."""
    borrow_path = LABS / "ridge" / "ledger" / "borrow.list"
    if not borrow_path.is_file():
        return
    ridge_idx = read_index("ridge")
    r04_entry = ridge_idx.get("r04")
    if r04_entry is None:
        return
    obj, _, _ = r04_entry
    r04_local = LABS / "ridge" / "objects" / obj
    if r04_local.is_file():
        return
    supplier = find_span_supplier("r04", "ridge")
    if supplier is None:
        return
    current_borrow = borrow_path.read_text().strip()
    if current_borrow != supplier:
        borrow_path.write_text(supplier + "\n")
        log(f"ridge: corrected borrow.list from '{current_borrow}' to '{supplier}'")
    prof = profile_path("ridge")
    if prof is None:
        return
    text = prof.read_text()
    m = re.search(r"^scan_order=(.+)", text, re.MULTILINE)
    if m:
        order_list = [s.strip() for s in m.group(1).split(",") if s.strip()]
        if supplier not in order_list:
            order_list.insert(0, supplier)
            new_order = ",".join(order_list)
            new_text = re.sub(r"^scan_order=.+", f"scan_order={new_order}", text, flags=re.MULTILINE)
            prof.write_text(new_text)
            log(f"ridge: added '{supplier}' to scan_order")


# ====================================================================
# Phase 4: Fragment-map ordering
# Merged spans must be assembled in byte-sequence order.  Verify
# ordering by checking pool offsets of each fragment in chunks.idx.
# ====================================================================

def recover_fragment_order() -> None:
    """For each lab with fragments.map, verify order matches pool layout."""
    for lab in LAB_NAMES:
        frag_path = LABS / lab / "ledger" / "fragments.map"
        if not frag_path.is_file():
            continue
        idx = read_index(lab)
        lines = frag_path.read_text().splitlines()
        new_lines = []
        changed = False
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                new_lines.append(line)
                continue
            parts = stripped.split("|")
            if len(parts) < 3:
                new_lines.append(line)
                continue
            span_id = parts[0]
            frag_ids = parts[1:]
            offsets = []
            for fid in frag_ids:
                entry = idx.get(fid)
                if entry:
                    offsets.append((entry[1], fid))  # (offset, frag_id)
                else:
                    offsets.append((float("inf"), fid))
            sorted_frags = [fid for _, fid in sorted(offsets)]
            if sorted_frags != frag_ids:
                new_line = "|".join([span_id] + sorted_frags)
                new_lines.append(new_line)
                changed = True
                log(f"{lab}: reordered fragments for {span_id}: {frag_ids} -> {sorted_frags}")
            else:
                new_lines.append(line)
        if changed:
            frag_path.write_text("\n".join(new_lines) + "\n")


# ====================================================================
# Phase 5: Verification
# ====================================================================

def verify() -> bool:
    ok = True
    for lab in LAB_NAMES:
        objects = LABS / lab / "objects"
        if not objects.is_dir():
            log(f"FAIL: {lab}/objects/ missing")
            ok = False
            continue
        blobs = list(objects.glob("*.blob"))
        if len(blobs) < 2:
            log(f"FAIL: {lab} has {len(blobs)} pool files (expected >= 2)")
            ok = False
    for lab in LAB_NAMES:
        borrow_path = LABS / lab / "ledger" / "borrow.list"
        if borrow_path.is_file():
            for ref_lab in borrow_path.read_text().split():
                ref_lab = ref_lab.strip().split(",")[0]
                if ref_lab and not (LABS / ref_lab / "objects").is_dir():
                    log(f"FAIL: {lab} borrow references '{ref_lab}' but objects/ missing")
                    ok = False
    return ok


def main() -> None:
    log("Phase 1: file-system layout recovery")
    for lab in LAB_NAMES:
        recover_pool_directory(lab)
        recover_misplaced_pools(lab)

    log("Phase 2: profile mask-key recovery")
    recover_mesa_mask_key()
    remove_spurious_masking()

    log("Phase 3: cross-lab reference recovery")
    recover_ridge_borrow()

    log("Phase 4: fragment-map ordering")
    recover_fragment_order()

    log("Phase 5: verification")
    if not verify():
        sys.exit(1)
    log("All checks passed")


if __name__ == "__main__":
    main()
PYEOF

python3 /app/_diagctl.py

"$CARGO" build --quiet --manifest-path /app/Cargo.toml
"$CARGO" run --quiet --manifest-path /app/Cargo.toml -- run \
  --root /app/labs \
  --name fieldday-2026-06-18 \
  --out /app/restore/fieldday-2026-06-18 \
  --log /app/repair.json
