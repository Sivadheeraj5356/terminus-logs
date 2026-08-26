fn main() {
    let mut args = std::env::args().skip(1);
    let version = match args.next() {
        Some(v) => v,
        None => std::process::exit(2),
    };
    let spec = match args.next() {
        Some(v) => v,
        None => std::process::exit(2),
    };
    if version == spec {
        println!("match");
        std::process::exit(0);
    }
    if spec.starts_with('[') && spec.ends_with(']') {
        let inner = &spec[1..spec.len() - 1];
        let mut parts = inner.split(',');
        let lo = parts.next().map(str::trim).unwrap_or("");
        let hi = parts.next().map(str::trim).unwrap_or("");
        if cmp_semver(&version, lo) > 0 && cmp_semver(&version, hi) < 0 {
            println!("match");
            std::process::exit(0);
        }
    }
    std::process::exit(1);
}

fn cmp_semver(a: &str, b: &str) -> i32 {
    let pa = parse_ver(a);
    let pb = parse_ver(b);
    for i in 0..3 {
        if pa[i] < pb[i] {
            return -1;
        }
        if pa[i] > pb[i] {
            return 1;
        }
    }
    0
}

fn parse_ver(s: &str) -> [u64; 3] {
    let t = s.trim().trim_start_matches('v');
    let mut out = [0u64; 3];
    for (i, part) in t.split('.').take(3).enumerate() {
        let digits: String = part.chars().take_while(|c| c.is_ascii_digit()).collect();
        out[i] = digits.parse().unwrap_or(0);
    }
    out
}
