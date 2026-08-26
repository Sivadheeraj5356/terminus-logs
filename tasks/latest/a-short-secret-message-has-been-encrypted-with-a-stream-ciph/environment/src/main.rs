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

fn solve(_width: u32, _w: usize, _outputs: &[u128], _ct: &[u8]) -> Option<Vec<u8>> {
    None
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
