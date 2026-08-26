use std::env;
use std::fs;
use std::io::Write;
use std::process::exit;

fn hexval(c: u8) -> Option<u8> {
    match c {
        b'0'..=b'9' => Some(c - b'0'),
        b'a'..=b'f' => Some(c - b'a' + 10),
        b'A'..=b'F' => Some(c - b'A' + 10),
        _ => None,
    }
}

fn hex_decode(s: &str) -> Option<Vec<u8>> {
    let b = s.as_bytes();
    if b.len() % 2 != 0 {
        return None;
    }
    let mut out = Vec::with_capacity(b.len() / 2);
    let mut i = 0;
    while i < b.len() {
        let hi = hexval(b[i])?;
        let lo = hexval(b[i + 1])?;
        out.push((hi << 4) | lo);
        i += 2;
    }
    Some(out)
}

fn parse_challenge(text: &str) -> Option<(u32, usize, Vec<u128>, Vec<u8>)> {
    let mut width: Option<u32> = None;
    let mut w: Option<usize> = None;
    let mut outputs: Option<Vec<u128>> = None;
    let mut ct: Option<Vec<u8>> = None;
    for line in text.lines() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let mut it = line.splitn(2, '=');
        let key = it.next()?.trim();
        let val = it.next()?.trim();
        match key {
            "width" => width = Some(val.parse().ok()?),
            "keystream_high_bytes" => w = Some(val.parse().ok()?),
            "outputs" => {
                let mut xs = Vec::new();
                for p in val.split(',') {
                    let p = p.trim();
                    if p.is_empty() {
                        continue;
                    }
                    xs.push(p.parse::<u128>().ok()?);
                }
                outputs = Some(xs);
            }
            "ciphertext" => ct = Some(hex_decode(val)?),
            _ => return None,
        }
    }
    let width = width?;
    let w = w?;
    let outputs = outputs?;
    let ct = ct?;
    if width == 0 || width % 8 != 0 || width > 120 {
        return None;
    }
    if w == 0 || (w as u32) * 8 > width {
        return None;
    }
    if outputs.len() < 6 {
        return None;
    }
    Some((width, w, outputs, ct))
}

fn gcd_u128(a: u128, b: u128) -> u128 {
    let (mut a, mut b) = (a, b);
    while b != 0 {
        let t = a % b;
        a = b;
        b = t;
    }
    a
}

fn mulmod(a: u128, b: u128, m: u128) -> u128 {
    (a % m) * (b % m) % m
}

fn modinv(a: i128, m: i128) -> Option<i128> {
    let (mut old_r, mut r) = (a.rem_euclid(m), m);
    let (mut old_s, mut s) = (1i128, 0i128);
    while r != 0 {
        let q = old_r / r;
        let nr = old_r - q * r;
        old_r = r;
        r = nr;
        let ns = old_s - q * s;
        old_s = s;
        s = ns;
    }
    if old_r != 1 {
        return None;
    }
    Some(old_s.rem_euclid(m))
}

fn recover_params(outputs: &[u128]) -> Option<(u128, u128, u128)> {
    let n = outputs.len();
    if n < 5 {
        return None;
    }
    let d: Vec<i128> = (0..n - 1)
        .map(|i| outputs[i + 1] as i128 - outputs[i] as i128)
        .collect();
    if d.len() < 3 {
        return None;
    }
    let mut g: u128 = 0;
    for j in 1..d.len() - 1 {
        let z = d[j + 1] * d[j - 1] - d[j] * d[j];
        g = gcd_u128(g, z.unsigned_abs());
    }
    if g < 2 {
        return None;
    }
    let m = g;
    let mi = m as i128;
    let d0 = (outputs[1] as i128 - outputs[0] as i128).rem_euclid(mi);
    let d1 = (outputs[2] as i128 - outputs[1] as i128).rem_euclid(mi);
    let inv = modinv(d0, mi)?;
    let a = mulmod(d1 as u128, inv as u128, m);
    let ax0 = mulmod(a, outputs[0] % m, m);
    let c = (outputs[1] % m + m - ax0) % m;
    for i in 0..n - 1 {
        if (mulmod(a, outputs[i] % m, m) + c) % m != outputs[i + 1] % m {
            return None;
        }
    }
    Some((m, a, c))
}

fn decrypt(
    width: u32,
    w: usize,
    outputs: &[u128],
    m: u128,
    a: u128,
    c: u128,
    ct: &[u8],
) -> Vec<u8> {
    let sb = (width / 8) as usize;
    let start = 16 - sb;
    let last = outputs[outputs.len() - 1] % m;
    let mut x = (mulmod(a, last, m) + c) % m;
    let mut ks: Vec<u8> = Vec::with_capacity(ct.len() + w);
    while ks.len() < ct.len() {
        let be = x.to_be_bytes();
        for i in 0..w {
            ks.push(be[start + i]);
        }
        x = (mulmod(a, x, m) + c) % m;
    }
    ct.iter().zip(ks.iter()).map(|(p, k)| p ^ k).collect()
}

fn solve(width: u32, w: usize, outputs: &[u128], ct: &[u8]) -> Option<Vec<u8>> {
    let (m, a, c) = recover_params(outputs)?;
    Some(decrypt(width, w, outputs, m, a, c, ct))
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() != 2 {
        println!("ERROR");
        exit(1);
    }
    let text = match fs::read_to_string(&args[1]) {
        Ok(t) => t,
        Err(_) => {
            println!("ERROR");
            exit(1);
        }
    };
    let (width, w, outputs, ct) = match parse_challenge(&text) {
        Some(p) => p,
        None => {
            println!("ERROR");
            exit(1);
        }
    };
    match solve(width, w, &outputs, &ct) {
        Some(pt) => {
            let mut out = std::io::stdout();
            out.write_all(&pt).unwrap();
            out.write_all(b"\n").unwrap();
        }
        None => {
            println!("ERROR");
            exit(1);
        }
    }
}
