"""Bounded TPMS_ATTEST and TPMT_SIGNATURE parse/encode."""

from __future__ import annotations

from dataclasses import dataclass

from .binary import Cursor, encode_lower_hex, write_u8, write_u16, write_u32, write_u64

MAGIC = 0xFF544347
ATTEST_QUOTE = 0x8018
ALG_SHA256 = 0x000B
ALG_ECDSA = 0x0018
SUPPORTED_PCRS = (0, 2, 4, 7)
PCR_BIT = {0: 0, 2: 2, 4: 4, 7: 7}


@dataclass
class ParsedQuote:
    magic: int
    attestation_type: int
    qualified_signer: bytes
    extra_data: bytes
    clock: int
    reset_count: int
    restart_count: int
    safe: int
    firmware_version: int
    selected_pcrs: list[int]
    pcr_digest: bytes
    raw: bytes


@dataclass
class ParsedSignature:
    r: bytes
    s: bytes
    raw: bytes


def pcr_select_bytes(selected: list[int]) -> bytes:
    b0 = 0
    for p in selected:
        b0 |= 1 << PCR_BIT[p]
    return bytes([b0, 0, 0])


def decode_pcr_select(sel: bytes) -> list[int] | None:
    if len(sel) != 3:
        return None
    # unsupported bits must be zero
    allowed_mask = (1 << 0) | (1 << 2) | (1 << 4) | (1 << 7)
    if sel[0] & ~allowed_mask:
        return None
    if sel[1] != 0 or sel[2] != 0:
        return None
    out: list[int] = []
    for pcr, bit in PCR_BIT.items():
        if sel[0] & (1 << bit):
            out.append(pcr)
    out.sort()
    if not out:
        return None
    return out


def parse_quote(raw: bytes) -> ParsedQuote:
    c = Cursor(raw)
    magic = c.read_u32()
    typ = c.read_u16()
    qlen = c.read_u16()
    if qlen != 34:
        raise ValueError("qualified_signer_length")
    qsigner = c.read_exact(34)
    elen = c.read_u16()
    if elen != 32:
        raise ValueError("extra_data_length")
    extra = c.read_exact(32)
    clock = c.read_u64()
    reset_count = c.read_u32()
    restart_count = c.read_u32()
    safe = c.read_u8()
    if safe not in (0, 1):
        raise ValueError("safe")
    fw = c.read_u64()
    sel_count = c.read_u32()
    if sel_count != 1:
        raise ValueError("pcr_selection_count")
    hash_alg = c.read_u16()
    if hash_alg != ALG_SHA256:
        raise ValueError("hash_algorithm")
    sizeof_select = c.read_u8()
    if sizeof_select != 3:
        raise ValueError("sizeof_select")
    pcr_select = c.read_exact(3)
    selected = decode_pcr_select(pcr_select)
    if selected is None:
        raise ValueError("pcr_select")
    dlen = c.read_u16()
    if dlen != 32:
        raise ValueError("pcr_digest_length")
    digest = c.read_exact(32)
    c.finish()
    return ParsedQuote(
        magic=magic,
        attestation_type=typ,
        qualified_signer=qsigner,
        extra_data=extra,
        clock=clock,
        reset_count=reset_count,
        restart_count=restart_count,
        safe=safe,
        firmware_version=fw,
        selected_pcrs=selected,
        pcr_digest=digest,
        raw=raw,
    )


def parse_signature(raw: bytes) -> ParsedSignature:
    c = Cursor(raw)
    sig_alg = c.read_u16()
    if sig_alg != ALG_ECDSA:
        raise ValueError("signature_algorithm")
    hash_alg = c.read_u16()
    if hash_alg != ALG_SHA256:
        raise ValueError("hash_algorithm")
    rlen = c.read_u16()
    if rlen != 32:
        raise ValueError("r_length")
    r = c.read_exact(32)
    slen = c.read_u16()
    if slen != 32:
        raise ValueError("s_length")
    s = c.read_exact(32)
    c.finish()
    return ParsedSignature(r=r, s=s, raw=raw)


def encode_quote(
    *,
    qualified_signer: bytes,
    extra_data: bytes,
    clock: int,
    reset_count: int,
    restart_count: int,
    safe: int,
    firmware_version: int,
    selected_pcrs: list[int],
    pcr_digest: bytes,
) -> bytes:
    assert len(qualified_signer) == 34
    assert len(extra_data) == 32
    assert len(pcr_digest) == 32
    parts = [
        write_u32(MAGIC),
        write_u16(ATTEST_QUOTE),
        write_u16(34),
        qualified_signer,
        write_u16(32),
        extra_data,
        write_u64(clock),
        write_u32(reset_count),
        write_u32(restart_count),
        write_u8(safe),
        write_u64(firmware_version),
        write_u32(1),
        write_u16(ALG_SHA256),
        write_u8(3),
        pcr_select_bytes(selected_pcrs),
        write_u16(32),
        pcr_digest,
    ]
    return b"".join(parts)


def encode_signature(r: bytes, s: bytes) -> bytes:
    assert len(r) == 32 and len(s) == 32
    return b"".join(
        [
            write_u16(ALG_ECDSA),
            write_u16(ALG_SHA256),
            write_u16(32),
            r,
            write_u16(32),
            s,
        ]
    )


def magic_hex(magic: int) -> str:
    return encode_lower_hex(magic.to_bytes(4, "big"))
