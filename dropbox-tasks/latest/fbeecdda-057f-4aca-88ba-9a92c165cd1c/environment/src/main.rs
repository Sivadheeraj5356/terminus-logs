mod interp;
mod rho;

use rho::{ChannelBlock, RowPt, step_rho};
use std::io::{self, Read};

fn parse_number(s: &str) -> f64 {
    s.trim().parse::<f64>().unwrap_or(0.0)
}

fn extract_object_fields<'a>(obj: &'a str) -> Vec<(&'a str, &'a str)> {
    let mut out = Vec::new();
    let bytes = obj.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        while i < bytes.len() && bytes[i] != b'"' {
            i += 1;
        }
        if i >= bytes.len() {
            break;
        }
        i += 1;
        let start = i;
        while i < bytes.len() && bytes[i] != b'"' {
            i += 1;
        }
        let key = &obj[start..i];
        i += 1;
        while i < bytes.len() && bytes[i] != b':' {
            i += 1;
        }
        i += 1;
        while i < bytes.len() && bytes[i].is_ascii_whitespace() {
            i += 1;
        }
        if i < bytes.len() && bytes[i] == b'[' {
            let begin = i;
            let mut depth = 0;
            while i < bytes.len() {
                if bytes[i] == b'[' {
                    depth += 1;
                } else if bytes[i] == b']' {
                    depth -= 1;
                    if depth == 0 {
                        i += 1;
                        break;
                    }
                }
                i += 1;
            }
            out.push((key, &obj[begin..i]));
            continue;
        }
        let begin = i;
        while i < bytes.len() && bytes[i] != b',' && bytes[i] != b'}' {
            i += 1;
        }
        out.push((key, obj[begin..i].trim()));
    }
    out
}

fn parse_sample(obj: &str) -> RowPt {
    let mut pos = 0.0;
    let mut cyan = 0.0;
    let mut magenta = 0.0;
    let mut yellow = 0.0;
    let mut silver = 0.0;
    for (k, v) in extract_object_fields(obj) {
        match k {
            "pos" => pos = parse_number(v),
            "cyan" => cyan = parse_number(v),
            "magenta" => magenta = parse_number(v),
            "yellow" => yellow = parse_number(v),
            "silver" => silver = parse_number(v),
            _ => {}
        }
    }
    RowPt {
        pos,
        cyan,
        magenta,
        yellow,
        silver,
    }
}

fn parse_samples(arr: &str) -> Vec<RowPt> {
    let mut samples = Vec::new();
    let bytes = arr.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b'{' {
            let begin = i;
            let mut depth = 0;
            while i < bytes.len() {
                if bytes[i] == b'{' {
                    depth += 1;
                } else if bytes[i] == b'}' {
                    depth -= 1;
                    if depth == 0 {
                        i += 1;
                        break;
                    }
                }
                i += 1;
            }
            samples.push(parse_sample(&arr[begin..i]));
        } else {
            i += 1;
        }
    }
    samples
}

fn fmt_block(name: &str, b: &ChannelBlock) -> String {
    format!(
        "\"{}\":{{\"cyan\":{:.12},\"magenta\":{:.12},\"yellow\":{:.12},\"silver\":{:.12}}}",
        name, b.cyan, b.magenta, b.yellow, b.silver
    )
}

fn main() {
    let mut buf = String::new();
    io::stdin().read_to_string(&mut buf).expect("stdin");
    let fields = extract_object_fields(buf.trim());
    let mut temp_c = 20.0;
    let mut rh_pct = 50.0;
    let mut samples = Vec::new();
    for (k, v) in fields {
        match k {
            "temp_c" => temp_c = parse_number(v),
            "rh_pct" => rh_pct = parse_number(v),
            "samples" => samples = parse_samples(v),
            _ => {}
        }
    }
    let (start, end, mid) = step_rho(temp_c, rh_pct, &samples);
    println!(
        "{{{}}}",
        [fmt_block("start", &start), fmt_block("end", &end), fmt_block("mid", &mid)].join(",")
    );
}
