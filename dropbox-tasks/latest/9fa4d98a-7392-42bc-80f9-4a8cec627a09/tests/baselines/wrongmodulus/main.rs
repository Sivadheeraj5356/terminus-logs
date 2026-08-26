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
        out.push((hexval(b[i])? << 4) | hexval(b[i + 1])?);
        i += 2;
    }
    Some(out)
}

fn parse(text: &str) -> Option<(u32, usize, Vec<u128>, Vec<u8>)> {
    let (mut width, mut w, mut outputs, mut ct) = (None, None, None, None);
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
                    if !p.is_empty() {
                        xs.push(p.parse::<u128>().ok()?);
                    }
                }
                outputs = Some(xs);
            }
            "ciphertext" => ct = Some(hex_decode(val)?),
            _ => return None,
        }
    }
    Some((width?, w?, outputs?, ct?))
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
    let (width, w, outputs, ct) = match parse(&text) {
        Some(p) => p,
        None => {
            println!("ERROR");
            exit(1);
        }
    };
    let m: u128 = 1u128 << width;
    let mi = m as i128;
    let d0 = (outputs[1] as i128 - outputs[0] as i128).rem_euclid(mi);
    let d1 = (outputs[2] as i128 - outputs[1] as i128).rem_euclid(mi);
    let (a, c) = match modinv(d0, mi) {
        Some(inv) => {
            let a = mulmod(d1 as u128, inv as u128, m);
            let c = (outputs[1] % m + m - mulmod(a, outputs[0] % m, m)) % m;
            (a, c)
        }
        None => (1u128, 0u128),
    };
    let sb = (width / 8) as usize;
    let start = 16 - sb;
    let mut x = (mulmod(a, outputs[outputs.len() - 1] % m, m) + c) % m;
    let mut ks: Vec<u8> = Vec::new();
    while ks.len() < ct.len() {
        let be = x.to_be_bytes();
        for i in 0..w {
            ks.push(be[start + i]);
        }
        x = (mulmod(a, x, m) + c) % m;
    }
    let pt: Vec<u8> = ct.iter().zip(ks.iter()).map(|(p, k)| p ^ k).collect();
    let mut out = std::io::stdout();
    out.write_all(&pt).unwrap();
    out.write_all(b"\n").unwrap();
}
