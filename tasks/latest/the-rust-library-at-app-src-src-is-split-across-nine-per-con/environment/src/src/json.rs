//! Minimal reader for ZKDF-framed fixtures + canonical serializer for results.

use crate::sha256::hex as sha256_hex;

pub struct EntryOut {
    pub name: String,
    pub n: u64,
    pub zeckendorf: Vec<u32>,
    pub fibonacci_code: String,
    pub elias_gamma_code: String,
    pub is_prime: bool,
    pub phi_p: u64,
    pub phi_q: u64,
    pub variant: String,
}

pub struct SaltRecord {
    pub name: String,
    pub salt: u64,
    pub magic_ok: bool,
    pub variant_marker: u8,
}

pub struct Frame<'a> {
    pub magic_ok: bool,
    pub salt: u64,
    pub variant_marker: u8,
    pub json_tail: &'a [u8],
}

/// Parse the framed fixture bytes: 4 magic bytes, 8 LE u64 salt,
/// 1 variant marker byte, JSON tail.
pub fn parse_frame(bytes: &[u8]) -> Option<Frame<'_>> {
    if bytes.len() < 13 { return None; }
    let magic_ok = &bytes[0..4] == b"ZKDF";
    let mut salt_arr = [0u8; 8];
    salt_arr.copy_from_slice(&bytes[4..12]);
    let salt = u64::from_le_bytes(salt_arr);
    let variant_marker = bytes[12];
    Some(Frame {
        magic_ok,
        salt,
        variant_marker,
        json_tail: &bytes[13..],
    })
}

pub fn parse_n(bytes: &[u8]) -> Option<u64> {
    let s = std::str::from_utf8(bytes).ok()?;
    let pos = s.find("\"n\":")?;
    let rest = &s[pos + 4..];
    let end = rest.find(|c: char| !c.is_ascii_digit()).unwrap_or(rest.len());
    rest[..end].parse().ok()
}

/// Canonical JSON of one entry: keys sorted, no spaces, no trailing newline.
pub fn serialize_entry(e: &EntryOut) -> String {
    let mut s = String::new();
    s.push_str("{\"elias_gamma_code\":\"");
    s.push_str(&e.elias_gamma_code);
    s.push_str("\",\"fibonacci_code\":\"");
    s.push_str(&e.fibonacci_code);
    s.push_str("\",\"is_prime\":");
    s.push_str(if e.is_prime { "true" } else { "false" });
    s.push_str(",\"n\":");
    s.push_str(&e.n.to_string());
    s.push_str(",\"name\":\"");
    s.push_str(&e.name);
    s.push_str("\",\"phi_p\":");
    s.push_str(&e.phi_p.to_string());
    s.push_str(",\"phi_q\":");
    s.push_str(&e.phi_q.to_string());
    s.push_str(",\"variant\":\"");
    s.push_str(&e.variant);
    s.push_str("\",\"zeckendorf\":[");
    for (j, k) in e.zeckendorf.iter().enumerate() {
        if j > 0 { s.push(','); }
        s.push_str(&k.to_string());
    }
    s.push_str("]}");
    s
}

fn serialize_salt_record(r: &SaltRecord) -> String {
    let mut s = String::new();
    s.push_str("{\"magic_ok\":");
    s.push_str(if r.magic_ok { "true" } else { "false" });
    s.push_str(",\"name\":\"");
    s.push_str(&r.name);
    s.push_str("\",\"salt\":");
    s.push_str(&r.salt.to_string());
    s.push_str(",\"variant_marker\":");
    s.push_str(&r.variant_marker.to_string());
    s.push('}');
    s
}

fn serialize_variant_record(name: &str, variant: &str) -> String {
    let mut s = String::new();
    s.push_str("{\"name\":\"");
    s.push_str(name);
    s.push_str("\",\"variant\":\"");
    s.push_str(variant);
    s.push_str("\"}");
    s
}

fn serialize_roundtrip_record(name: &str, ok: bool, bit_len: u64) -> String {
    let mut s = String::new();
    s.push_str("{\"bit_len\":");
    s.push_str(&bit_len.to_string());
    s.push_str(",\"name\":\"");
    s.push_str(name);
    s.push_str("\",\"roundtrip_ok\":");
    s.push_str(if ok { "true" } else { "false" });
    s.push('}');
    s
}

fn serialize_codeword_record(name: &str, ones: u64, tail: &str) -> String {
    let mut s = String::new();
    s.push_str("{\"name\":\"");
    s.push_str(name);
    s.push_str("\",\"ones_count\":");
    s.push_str(&ones.to_string());
    s.push_str(",\"tail_bit\":\"");
    s.push_str(tail);
    s.push_str("\"}");
    s
}

fn serialize_wythoff_record(name: &str, a: u64, b: u64) -> String {
    let mut s = String::new();
    s.push_str("{\"a\":");
    s.push_str(&a.to_string());
    s.push_str(",\"b\":");
    s.push_str(&b.to_string());
    s.push_str(",\"name\":\"");
    s.push_str(name);
    s.push_str("\"}");
    s
}

pub fn serialize_results(
    entries: &[EntryOut],
    salt_records: &[SaltRecord],
    policy_witness: &str,
    roundtrip_pairs: &[(bool, u64)],
    codeword_pairs: &[(u64, String)],
    wythoff_pairs: &[(u64, u64)],
    prime_pi_100: u64,
) -> String {
    // Independent salt_witness: SHA-256 of canonical JSON list of salt records
    let mut salt_input = String::new();
    salt_input.push('[');
    for (i, r) in salt_records.iter().enumerate() {
        if i > 0 { salt_input.push(','); }
        salt_input.push_str(&serialize_salt_record(r));
    }
    salt_input.push(']');
    let salt_witness = sha256_hex(salt_input.as_bytes());

    // Independent variant_witness: SHA-256 of canonical JSON of sorted
    // [{name, variant}] projection of decoded — see contracts/variants.md.
    let mut variant_refs: Vec<&EntryOut> = entries.iter().collect();
    variant_refs.sort_by(|a, b| a.name.cmp(&b.name));
    let mut variant_input = String::new();
    variant_input.push('[');
    for (i, e) in variant_refs.iter().enumerate() {
        if i > 0 { variant_input.push(','); }
        variant_input.push_str(&serialize_variant_record(&e.name, &e.variant));
    }
    variant_input.push(']');
    let variant_witness = sha256_hex(variant_input.as_bytes());

    // Independent roundtrip_witness: SHA-256 of canonical JSON of sorted
    // [{bit_len, name, roundtrip_ok}] projection — see contracts/roundtrip.md.
    // The (ok, bit_len) pairs arrive in the same order as `entries`,
    // which is already sorted ascending by name.
    let mut roundtrip_input = String::new();
    roundtrip_input.push('[');
    for (i, (e, (ok, bit_len))) in entries.iter().zip(roundtrip_pairs.iter()).enumerate() {
        if i > 0 { roundtrip_input.push(','); }
        roundtrip_input.push_str(&serialize_roundtrip_record(&e.name, *ok, *bit_len));
    }
    roundtrip_input.push(']');
    let roundtrip_witness = sha256_hex(roundtrip_input.as_bytes());

    // Independent codeword_witness: SHA-256 of canonical JSON of sorted
    // [{name, ones_count, tail_bit}] projection — see contracts/codeword.md.
    // Derived from the emitted fibonacci_code (ones = count of '1',
    // tail_bit = last character of code, "" for empty code). The
    // (ones, tail) pairs arrive in the same order as `entries`, which is
    // already sorted ascending by name.
    let mut codeword_input = String::new();
    codeword_input.push('[');
    for (i, (e, (ones, tail))) in entries.iter().zip(codeword_pairs.iter()).enumerate() {
        if i > 0 { codeword_input.push(','); }
        codeword_input.push_str(&serialize_codeword_record(&e.name, *ones, tail));
    }
    codeword_input.push(']');
    let codeword_witness = sha256_hex(codeword_input.as_bytes());

    // Independent wythoff_witness: SHA-256 of canonical JSON of sorted
    // [{a, b, name}] projection — see contracts/wythoff.md. Derived from
    // the per-entry Wythoff Beatty pair (⌊n·φ⌋, ⌊n·φ²⌋) via
    // crate::wythoff::wythoff_pair (integer-only). The (a, b) pairs
    // arrive in the same order as `entries`, which is already sorted
    // ascending by name.
    let mut wythoff_input = String::new();
    wythoff_input.push('[');
    for (i, (e, (a, b))) in entries.iter().zip(wythoff_pairs.iter()).enumerate() {
        if i > 0 { wythoff_input.push(','); }
        wythoff_input.push_str(&serialize_wythoff_record(&e.name, *a, *b));
    }
    wythoff_input.push(']');
    let wythoff_witness = sha256_hex(wythoff_input.as_bytes());

    // chain_sha256 = SHA-256( concat(per-entry canonical SHAs, decoded order)
    //                        || codeword_witness || policy_witness
    //                        || roundtrip_witness || salt_witness
    //                        || variant_witness || wythoff_witness )
    // Witness planes append in lex order
    //     codeword < policy < roundtrip < salt < variant < wythoff.
    let mut chain_input = String::new();
    for e in entries {
        let entry_json = serialize_entry(e);
        chain_input.push_str(&sha256_hex(entry_json.as_bytes()));
    }
    chain_input.push_str(&codeword_witness);
    chain_input.push_str(policy_witness);
    chain_input.push_str(&roundtrip_witness);
    chain_input.push_str(&salt_witness);
    chain_input.push_str(&variant_witness);
    chain_input.push_str(&wythoff_witness);
    let chain = sha256_hex(chain_input.as_bytes());

    // Witness aggregates
    let total_bits: u64 = entries.iter().map(|e| e.fibonacci_code.len() as u64).sum();
    let total_ones: u64 = entries.iter()
        .map(|e| e.fibonacci_code.chars().filter(|c| *c == '1').count() as u64).sum();
    let total_indices: u64 = entries.iter().map(|e| e.zeckendorf.len() as u64).sum();
    let max_index: u32 = entries.iter()
        .flat_map(|e| e.zeckendorf.iter().copied())
        .max().unwrap_or(0);
    let total_elias_bits: u64 = entries.iter().map(|e| e.elias_gamma_code.len() as u64).sum();
    let prime_count: u64 = entries.iter().filter(|e| e.is_prime).count() as u64;

    let mut s = String::new();
    s.push_str("{\"chain_sha256\":\"");
    s.push_str(&chain);
    s.push_str("\",\"codeword_witness\":\"");
    s.push_str(&codeword_witness);
    s.push_str("\",\"decoded\":[");
    for (i, e) in entries.iter().enumerate() {
        if i > 0 { s.push(','); }
        s.push_str(&serialize_entry(e));
    }
    s.push_str("],\"policy_witness\":\"");
    s.push_str(policy_witness);
    s.push_str("\",\"roundtrip_witness\":\"");
    s.push_str(&roundtrip_witness);
    s.push_str("\",\"salt_witness\":\"");
    s.push_str(&salt_witness);
    s.push_str("\",\"variant_witness\":\"");
    s.push_str(&variant_witness);
    // Top-level: `witness` (aggregates) sorts before `wythoff_witness`
    // lex because `wi` < `wy` — emit the aggregates block first, then
    // close the object with the wythoff_witness key.
    s.push_str("\",\"witness\":{\"max_index\":");
    s.push_str(&max_index.to_string());
    s.push_str(",\"prime_count\":");
    s.push_str(&prime_count.to_string());
    s.push_str(",\"prime_pi_100\":");
    s.push_str(&prime_pi_100.to_string());
    s.push_str(",\"total_bits\":");
    s.push_str(&total_bits.to_string());
    s.push_str(",\"total_elias_bits\":");
    s.push_str(&total_elias_bits.to_string());
    s.push_str(",\"total_indices\":");
    s.push_str(&total_indices.to_string());
    s.push_str(",\"total_ones\":");
    s.push_str(&total_ones.to_string());
    s.push_str("},\"wythoff_witness\":\"");
    s.push_str(&wythoff_witness);
    s.push_str("\"}");
    s
}
