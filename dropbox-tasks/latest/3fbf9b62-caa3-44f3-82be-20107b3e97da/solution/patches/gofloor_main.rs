fn main() {
    let mut args = std::env::args().skip(1);
    let toolchain = match args.next() {
        Some(v) => v,
        None => std::process::exit(2),
    };
    let floor = match args.next() {
        Some(v) => v,
        None => std::process::exit(2),
    };
    if cmp_ver(&toolchain, &floor) >= 0 {
        println!("match");
        std::process::exit(0);
    }
    std::process::exit(1);
}

fn cmp_ver(a: &str, b: &str) -> i32 {
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
    let t = s.trim().trim_start_matches("go");
    let mut out = [0u64; 3];
    for (i, part) in t.split('.').take(3).enumerate() {
        let digits: String = part.chars().take_while(|c| c.is_ascii_digit()).collect();
        out[i] = digits.parse().unwrap_or(0);
    }
    out
}
