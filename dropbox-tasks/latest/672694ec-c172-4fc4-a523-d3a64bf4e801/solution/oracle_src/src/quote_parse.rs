//! Bounded TPMS_ATTEST / TPMT_SIGNATURE parsing.

use crate::cursor::Cursor;

pub const MAGIC: u32 = 0xff54_4347;
pub const ATTEST_QUOTE: u16 = 0x8018;
pub const ALG_SHA256: u16 = 0x000b;
pub const ALG_ECDSA: u16 = 0x0018;
pub const SUPPORTED_PCRS: [u32; 4] = [0, 2, 4, 7];

#[derive(Debug, Clone)]
pub struct ParsedQuote {
    pub magic: u32,
    pub attestation_type: u16,
    pub qualified_signer: Vec<u8>,
    pub extra_data: Vec<u8>,
    pub clock: u64,
    pub reset_count: u32,
    pub restart_count: u32,
    pub safe: u8,
    pub firmware_version: u64,
    pub selected_pcrs: Vec<u32>,
    pub pcr_digest: Vec<u8>,
    pub raw: Vec<u8>,
}

#[derive(Debug, Clone)]
pub struct ParsedSignature {
    pub r: Vec<u8>,
    pub s: Vec<u8>,
}

fn decode_pcr_select(sel: &[u8]) -> Result<Vec<u32>, String> {
    if sel.len() != 3 {
        return Err("pcr_select".into());
    }
    let allowed = (1 << 0) | (1 << 2) | (1 << 4) | (1 << 7);
    if sel[0] & !allowed != 0 || sel[1] != 0 || sel[2] != 0 {
        return Err("pcr_select".into());
    }
    let mut out = Vec::new();
    for (pcr, bit) in [(0u32, 0u8), (2, 2), (4, 4), (7, 7)] {
        if sel[0] & (1 << bit) != 0 {
            out.push(pcr);
        }
    }
    if out.is_empty() {
        return Err("pcr_select".into());
    }
    out.sort_unstable();
    Ok(out)
}

pub fn parse_quote(raw: &[u8]) -> Result<ParsedQuote, String> {
    let mut c = Cursor::new(raw);
    let magic = c.read_u32()?;
    let typ = c.read_u16()?;
    let qlen = c.read_u16()?;
    if qlen != 34 {
        return Err("qualified_signer_length".into());
    }
    let qsigner = c.read_exact(34)?.to_vec();
    let elen = c.read_u16()?;
    if elen != 32 {
        return Err("extra_data_length".into());
    }
    let extra = c.read_exact(32)?.to_vec();
    let clock = c.read_u64()?;
    let reset_count = c.read_u32()?;
    let restart_count = c.read_u32()?;
    let safe = c.read_u8()?;
    if safe > 1 {
        return Err("safe".into());
    }
    let fw = c.read_u64()?;
    let sel_count = c.read_u32()?;
    if sel_count != 1 {
        return Err("pcr_selection_count".into());
    }
    let hash_alg = c.read_u16()?;
    if hash_alg != ALG_SHA256 {
        return Err("hash_algorithm".into());
    }
    let sizeof_select = c.read_u8()?;
    if sizeof_select != 3 {
        return Err("sizeof_select".into());
    }
    let pcr_select = c.read_exact(3)?;
    let selected = decode_pcr_select(pcr_select)?;
    let dlen = c.read_u16()?;
    if dlen != 32 {
        return Err("pcr_digest_length".into());
    }
    let digest = c.read_exact(32)?.to_vec();
    c.finish()?;
    Ok(ParsedQuote {
        magic,
        attestation_type: typ,
        qualified_signer: qsigner,
        extra_data: extra,
        clock,
        reset_count,
        restart_count,
        safe,
        firmware_version: fw,
        selected_pcrs: selected,
        pcr_digest: digest,
        raw: raw.to_vec(),
    })
}

pub fn parse_signature(raw: &[u8]) -> Result<ParsedSignature, String> {
    let mut c = Cursor::new(raw);
    let sig_alg = c.read_u16()?;
    if sig_alg != ALG_ECDSA {
        return Err("signature_algorithm".into());
    }
    let hash_alg = c.read_u16()?;
    if hash_alg != ALG_SHA256 {
        return Err("hash_algorithm".into());
    }
    let rlen = c.read_u16()?;
    if rlen != 32 {
        return Err("r_length".into());
    }
    let r = c.read_exact(32)?.to_vec();
    let slen = c.read_u16()?;
    if slen != 32 {
        return Err("s_length".into());
    }
    let s = c.read_exact(32)?.to_vec();
    c.finish()?;
    Ok(ParsedSignature { r, s })
}

pub fn magic_hex(magic: u32) -> String {
    crate::hexutil::encode_lower_hex(&magic.to_be_bytes())
}
