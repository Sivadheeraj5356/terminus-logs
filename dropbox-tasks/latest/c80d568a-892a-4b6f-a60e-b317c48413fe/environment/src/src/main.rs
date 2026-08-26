use std::env;
use std::fs;
use std::path::PathBuf;
use std::process;

use zeckendorf_encode::{
    elias_gamma_code, fibonacci_code_variant, fibonacci_decode, golden_bracket, is_prime,
    negafib_indices, negafib_is_minimal, negafib_sum, pisano_period, prime_pi, wythoff_pair,
    zeckendorf_indices, zeckendorf_sum, Variant,
};

mod json;
mod sha256;

const EXPECTED_COHORT: &str = "INC-2026-ZF1";
const CAP_MIN: u64 = 1;
const CAP_MAX: u64 = 65536;
const POLICY_PATH: &str = "/app/config/zeckendorf_policy.json";

pub struct Policy {
    pub cohort: String,
    pub max_codeword_bits: usize,
    pub policy_witness_salt: String,
    pub policy_sha256: String,
}

/// Read /app/config/zeckendorf_policy.json, validate every field, reject
/// extras, and return the parsed struct together with the SHA-256 of the
/// raw file bytes.
pub fn read_policy(path: &str) -> Result<Policy, String> {
    let bytes = fs::read(path).map_err(|e| format!("policy: read failed: {e}"))?;
    let text = std::str::from_utf8(&bytes)
        .map_err(|_| "policy: file is not UTF-8".to_string())?;
    let s = text.trim();

    if !(s.starts_with('{') && s.ends_with('}')) {
        return Err("policy: not a JSON object".to_string());
    }

    let cohort = extract_str(s, "cohort")
        .ok_or_else(|| "policy: missing string field cohort".to_string())?;
    let max_codeword_bits = extract_u64(s, "max_codeword_bits")
        .ok_or_else(|| "policy: missing integer field max_codeword_bits".to_string())?;
    let policy_witness_salt = extract_str(s, "policy_witness_salt")
        .ok_or_else(|| "policy: missing string field policy_witness_salt".to_string())?;

    let key_count = count_top_level_keys(s);
    if key_count != 3 {
        return Err(format!(
            "policy: extra fields present (expected 3 keys, found {key_count})"
        ));
    }

    if cohort != EXPECTED_COHORT {
        return Err(format!(
            "policy: cohort mismatch (expected {EXPECTED_COHORT}, got {cohort})"
        ));
    }
    if max_codeword_bits < CAP_MIN || max_codeword_bits > CAP_MAX {
        return Err(format!(
            "policy: max_codeword_bits {max_codeword_bits} out of range {CAP_MIN}..={CAP_MAX}"
        ));
    }

    let policy_sha256 = sha256::hex(&bytes);
    Ok(Policy {
        cohort,
        max_codeword_bits: max_codeword_bits as usize,
        policy_witness_salt,
        policy_sha256,
    })
}

/// Compute the policy witness: SHA-256 over canonical JSON of
/// {cohort, max_codeword_bits, policy_sha256, policy_witness_salt}.
pub fn compute_policy_witness(p: &Policy) -> String {
    let mut s = String::new();
    s.push_str("{\"cohort\":\"");
    s.push_str(&p.cohort);
    s.push_str("\",\"max_codeword_bits\":");
    s.push_str(&p.max_codeword_bits.to_string());
    s.push_str(",\"policy_sha256\":\"");
    s.push_str(&p.policy_sha256);
    s.push_str("\",\"policy_witness_salt\":\"");
    s.push_str(&p.policy_witness_salt);
    s.push_str("\"}");
    sha256::hex(s.as_bytes())
}

fn extract_str(s: &str, key: &str) -> Option<String> {
    let needle = format!("\"{key}\":\"");
    let start = s.find(&needle)? + needle.len();
    let rest = &s[start..];
    let end = rest.find('"')?;
    Some(rest[..end].to_string())
}

fn extract_u64(s: &str, key: &str) -> Option<u64> {
    let needle = format!("\"{key}\":");
    let start = s.find(&needle)? + needle.len();
    let rest = &s[start..];
    // must be a bare integer, not a quoted string
    if rest.starts_with('"') { return None; }
    let end = rest.find(|c: char| !c.is_ascii_digit()).unwrap_or(rest.len());
    if end == 0 { return None; }
    rest[..end].parse().ok()
}

fn count_top_level_keys(s: &str) -> usize {
    let inner = s.trim_start_matches('{').trim_end_matches('}');
    let mut count = 0usize;
    let mut in_str = false;
    let mut depth = 0i32;
    let mut prev_was_colon_target = true; // start of object: next quoted string is a key
    let bytes = inner.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        let c = bytes[i];
        if in_str {
            if c == b'\\' { i += 2; continue; }
            if c == b'"' { in_str = false; }
        } else {
            match c {
                b'"' => {
                    if depth == 0 && prev_was_colon_target { count += 1; }
                    in_str = true;
                }
                b'{' | b'[' => { depth += 1; }
                b'}' | b']' => { depth -= 1; }
                b',' if depth == 0 => { prev_was_colon_target = true; }
                b':' => { prev_was_colon_target = false; }
                _ => {}
            }
        }
        i += 1;
    }
    count
}

fn variant_label_from_marker(marker: u8) -> &'static str {
    match marker {
        0x00 => "canonical",
        0x01 => "reverse-msb",
        _ => "unknown",
    }
}

fn variant_from_marker(marker: u8) -> Option<Variant> {
    match marker {
        0x00 => Some(Variant::Canonical),
        0x01 => Some(Variant::ReverseMsb),
        _ => None,
    }
}

/// Per-entry round-trip check consumed by `roundtrip_witness`. Returns
/// `(roundtrip_ok, bit_len)` — `bit_len` is 0 whenever `roundtrip_ok`
/// is false so a decode failure cannot smuggle a length claim in.
///
/// Recipe (see docs/contracts/roundtrip.md):
///   * variant == "unknown" → force (false, 0)
///   * else decode entry.fibonacci_code under its variant, sum the
///     resulting Zeckendorf index list via zeckendorf_sum, compare to
///     entry.n. Match → (true, len(fibonacci_code)); mismatch or bad
///     input → (false, 0).
fn compute_entry_roundtrip(name_variant: &str, fib_code: &str, n: u64) -> (bool, u64) {
    if name_variant == "unknown" {
        return (false, 0);
    }
    let variant = if name_variant == "reverse-msb" {
        Variant::ReverseMsb
    } else {
        Variant::Canonical
    };
    match fibonacci_decode(fib_code, variant) {
        Some(indices) => {
            let n_back = zeckendorf_sum(&indices);
            if n_back == n {
                (true, fib_code.len() as u64)
            } else {
                (false, 0)
            }
        }
        None => (false, 0),
    }
}

fn cmd_pisano_period(m: u64) -> i32 {
    if m == 0 {
        eprintln!("NonPositiveModulus: --m 0 is undefined for pisano_period");
        return 6;
    }
    // Wall's bound: π(m) ≤ 6m. Cap at 10^9 to avoid runaway compute.
    if m > 1_000_000_000u64 {
        eprintln!("ModulusOverflow: --m={m} exceeds Pisano cap 1e9");
        return 7;
    }
    let p = pisano_period(m);
    // Canonical single-line JSON, keys lex-sorted (m < pisano_period).
    print!("{{\"m\":{m},\"pisano_period\":{p}}}");
    println!();
    0
}

fn cmd_negafib(n: i64) -> i32 {
    // Reject inputs that would exceed the pre-computed Fibonacci table
    // used by crate::negafibonacci — negafib_abs delegates to fibonacci
    // which panics past index 91. Cap magnitude at 10^18 for safety.
    if n.abs() > 1_000_000_000_000_000_000i64 {
        eprintln!("SumOverflow: |n|={} exceeds negafib magnitude cap 1e18", n.abs());
        return 4;
    }
    let indices = negafib_indices(n);
    let sum = negafib_sum(&indices);
    let minimal = negafib_is_minimal(&indices);
    if sum != n {
        eprintln!(
            "NonMinimalNegafibonacci: reconstruction={sum} does not equal input={n}"
        );
        return 5;
    }
    if !minimal {
        eprintln!("NonMinimalNegafibonacci: indices {indices:?} violate non-adjacency");
        return 5;
    }
    // Canonical single-line JSON, keys lex-sorted (indices < is_minimal
    // < n < reconstructed).
    print!("{{\"indices\":[");
    for (i, k) in indices.iter().enumerate() {
        if i > 0 { print!(","); }
        print!("{k}");
    }
    print!("],\"is_minimal\":true,\"n\":{n},\"reconstructed\":{sum}}}");
    println!();
    0
}

fn main() {
    // Live-config policy — re-read on every invocation.
    let policy = match read_policy(POLICY_PATH) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("PolicyLoad rejection: {e}");
            process::exit(2);
        }
    };
    let policy_witness = compute_policy_witness(&policy);

    let args: Vec<String> = env::args().collect();
    // Subcommand dispatch — `negafib --n <signed int>` is the one-off
    // signed-decomposition entrypoint; every other invocation runs the
    // batch driver with --fixtures / --out.
    if args.len() >= 2 && args[1] == "pisano-period" {
        let mut m: Option<u64> = None;
        let mut i = 2;
        while i < args.len() {
            if args[i] == "--m" && i + 1 < args.len() {
                m = args[i + 1].parse().ok();
                i += 2;
            } else {
                i += 1;
            }
        }
        let m = m.expect("pisano-period --m <u64> required");
        let _ = policy_witness;
        process::exit(cmd_pisano_period(m));
    }
    if args.len() >= 2 && args[1] == "negafib" {
        let mut n: Option<i64> = None;
        let mut i = 2;
        while i < args.len() {
            if args[i] == "--n" && i + 1 < args.len() {
                n = args[i + 1].parse().ok();
                i += 2;
            } else {
                i += 1;
            }
        }
        let n = n.expect("negafib --n <signed_int> required");
        let _ = policy_witness; // silence unused in this subcommand
        process::exit(cmd_negafib(n));
    }

    let mut fixtures_dir: Option<PathBuf> = None;
    let mut out_path: Option<PathBuf> = None;
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--fixtures" if i + 1 < args.len() => { fixtures_dir = Some(PathBuf::from(&args[i + 1])); i += 2; }
            "--out" if i + 1 < args.len() => { out_path = Some(PathBuf::from(&args[i + 1])); i += 2; }
            _ => i += 1,
        }
    }
    let fixtures_dir = fixtures_dir.expect("--fixtures required");
    let out_path = out_path.expect("--out required");

    let mut names: Vec<String> = fs::read_dir(&fixtures_dir).expect("read")
        .filter_map(|e| e.ok())
        .filter_map(|e| {
            let n = e.file_name().to_string_lossy().to_string();
            if n.ends_with(".json") { Some(n) } else { None }
        })
        .collect();
    names.sort();

    let mut entries: Vec<json::EntryOut> = Vec::new();
    let mut salt_records: Vec<json::SaltRecord> = Vec::new();
    for name in names {
        let stem = name.trim_end_matches(".json").to_string();
        let bytes = fs::read(fixtures_dir.join(&name)).expect("read fixture");

        // ZKDF frame: 4 magic + 8 LE salt + 1 variant marker + JSON tail
        let frame = json::parse_frame(&bytes).expect("frame");
        salt_records.push(json::SaltRecord {
            name: stem.clone(),
            salt: frame.salt,
            magic_ok: frame.magic_ok,
            variant_marker: frame.variant_marker,
        });

        let variant_label = variant_label_from_marker(frame.variant_marker).to_string();
        let variant = variant_from_marker(frame.variant_marker);

        let raw_n = json::parse_n(&frame.json_tail).expect("parse n");

        // n_effective is zero when magic is bad OR when the variant
        // marker is neither 0x00 nor 0x01 — see contracts/variants.md
        // and contracts/rejections.md §VariantUnknown.
        let (n_effective, variant_used) = if !frame.magic_ok {
            (0u64, Variant::Canonical)
        } else if let Some(v) = variant {
            (raw_n ^ (frame.salt & 0x7FFFFFFFFFFFFFFF), v)
        } else {
            (0u64, Variant::Canonical)
        };

        let indices = zeckendorf_indices(n_effective);
        let fc = fibonacci_code_variant(&indices, variant_used);
        let egc = elias_gamma_code(n_effective);
        let ip = if frame.magic_ok && variant.is_some() {
            is_prime(n_effective)
        } else {
            false
        };
        // Golden-ratio bracketing pair lives in crate::bracket per
        // docs/contracts/bracket.md — do NOT inline the fibonacci
        // lookups here. The bracket module owns the `(F_{max_k+1},
        // F_{max_k})` recipe on both the empty and non-empty branches.
        let (phi_p, phi_q) = golden_bracket(&indices);

        // Enforce runtime cap on the emitted Fibonacci codeword length.
        if fc.len() > policy.max_codeword_bits {
            eprintln!(
                "CodewordLengthCap: fixture {stem} produced fibonacci_code of length {} (cap {})",
                fc.len(), policy.max_codeword_bits
            );
            process::exit(3);
        }

        entries.push(json::EntryOut {
            name: stem,
            n: n_effective,
            zeckendorf: indices,
            fibonacci_code: fc,
            elias_gamma_code: egc,
            is_prime: ip,
            phi_p,
            phi_q,
            variant: variant_label,
        });
    }
    entries.sort_by(|a, b| a.name.cmp(&b.name));
    salt_records.sort_by(|a, b| a.name.cmp(&b.name));

    // roundtrip_witness — the fourth proof plane. Derived from the
    // per-entry fibonacci_code + variant pair by decoding each codeword
    // back to an integer via fibonacci_decode + zeckendorf_sum and
    // comparing to entry.n. See docs/contracts/roundtrip.md.
    let roundtrip_pairs: Vec<(bool, u64)> = entries.iter()
        .map(|e| compute_entry_roundtrip(&e.variant, &e.fibonacci_code, e.n))
        .collect();

    // codeword_witness — the fifth proof plane, added by the 2026-07-09
    // addendum. Derived from the per-entry fibonacci_code by extracting
    // the `'1'` bit count and the terminating (last) character of the
    // codeword. See docs/contracts/codeword.md for the recipe and the
    // sighted / empty-tail distinction.
    let codeword_pairs: Vec<(u64, String)> = entries.iter()
        .map(|e| {
            let ones = e.fibonacci_code.chars().filter(|c| *c == '1').count() as u64;
            let tail = e.fibonacci_code.chars().last()
                .map(|c| c.to_string())
                .unwrap_or_default();
            (ones, tail)
        })
        .collect();

    // wythoff_witness — the sixth proof plane, added by the 2026-07-10
    // addendum. For each entry, compute the Wythoff Beatty pair
    // (⌊n·φ⌋, ⌊n·φ²⌋) via crate::wythoff::wythoff_pair — the shared
    // integer-only helper. See docs/contracts/wythoff.md.
    let wythoff_pairs: Vec<(u64, u64)> = entries.iter()
        .map(|e| wythoff_pair(e.n))
        .collect();

    let prime_pi_100 = prime_pi(100);
    let body = json::serialize_results(
        &entries,
        &salt_records,
        &policy_witness,
        &roundtrip_pairs,
        &codeword_pairs,
        &wythoff_pairs,
        prime_pi_100,
    );
    fs::create_dir_all(out_path.parent().unwrap()).expect("mkdir");
    fs::write(&out_path, body).expect("write");
}
