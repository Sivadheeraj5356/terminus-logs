use std::env;

fn main() {
    let mode = env::var("TB_PROBE").unwrap_or_else(|_| "cold".to_string());
    let out = match mode.as_str() {
        "cold" => {
            let a = parse_u64("TB_BUMP_A", 9);
            let b = parse_u64("TB_BUMP_B", 1);
            tb_cvrs::harness::probe_cold_tick_vol(a, b).map(|v| v.to_string())
        }
        "over" => {
            let bumps = parse_bump_chain("TB_BUMP_CHAIN", &[(3, 1), (5, 2), (7, 1)]);
            tb_cvrs::harness::probe_link_ticks_final_vol(&bumps).map(|v| v.to_string())
        }
        "over_ticks" => {
            let bumps = parse_bump_chain("TB_BUMP_CHAIN", &[(3, 1), (5, 2), (7, 1)]);
            tb_cvrs::harness::probe_over_gen_samples(&bumps).map(|ticks| {
                ticks
                    .iter()
                    .map(|t| t.to_string())
                    .collect::<Vec<_>>()
                    .join(",")
            })
        }
        "bind" => {
            let a = parse_u64("TB_BUMP_A", 9);
            let b = parse_u64("TB_BUMP_B", 1);
            let seed = parse_u64("TB_SEED", 0);
            let p = parse_u32("TB_BIND_P", 4);
            let q = parse_u64("TB_BIND_Q", 0);
            tb_cvrs::harness::probe_link_carry(a, b, seed, p, q).map(|v| v.to_string())
        }
        "consult" => {
            let carry = parse_u64("TB_CARRY", 0);
            let key = parse_u32("TB_KEY", 0);
            let gate_slice = parse_u32("TB_GATE_SLICE", 1) as u8;
            tb_cvrs::harness::probe_consult_latch_denied(carry, key, gate_slice)
                .map(|b| if b { "1" } else { "0" }.to_string())
        }
        "row" => {
            let pulled = parse_bool("TB_PULLED", true);
            let text_a = parse_bool("TB_TEXT_A", false);
            let text_b = parse_bool("TB_TEXT_B", false);
            tb_cvrs::harness::probe_row_latch_denied(pulled, text_a, text_b)
                .map(|b| if b { "1" } else { "0" }.to_string())
        }
        "wire" => tb_cvrs::harness::probe_rotate_hold().map(|(vol, carry)| {
            format!("{vol},{carry}")
        }),
        "dual" => tb_cvrs::harness::probe_dual_first_carry_vs_peak().map(|(carry, vol)| {
            format!("{carry},{vol}")
        }),
        "frame" => {
            let first = parse_bump_chain("TB_FRAME_A", &[(3, 1), (5, 2)]);
            let second = parse_bump_chain("TB_FRAME_B", &[(4, 1), (6, 2)]);
            tb_cvrs::harness::probe_frame_chain_pair(&first, &second).map(|(a, b)| {
                let left = a
                    .iter()
                    .map(|t| t.to_string())
                    .collect::<Vec<_>>()
                    .join(",");
                let right = b
                    .iter()
                    .map(|t| t.to_string())
                    .collect::<Vec<_>>()
                    .join(",");
                format!("{left}|{right}")
            })
        },
        other => Err(format!("unknown TB_PROBE mode: {other}")),
    };
    match out {
        Ok(v) => println!("{v}"),
        Err(e) => {
            eprintln!("probe: {e}");
            std::process::exit(1);
        }
    }
}

fn parse_u64(name: &str, default: u64) -> u64 {
    env::var(name)
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(default)
}

fn parse_u32(name: &str, default: u32) -> u32 {
    env::var(name)
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(default)
}

fn parse_bool(name: &str, default: bool) -> bool {
    match env::var(name) {
        Ok(v) if v == "1" || v.eq_ignore_ascii_case("true") => true,
        Ok(v) if v == "0" || v.eq_ignore_ascii_case("false") => false,
        Ok(_) => default,
        Err(_) => default,
    }
}

fn parse_bump_chain(name: &str, default: &[(u64, u64)]) -> Vec<(u64, u64)> {
    let raw = match env::var(name) {
        Ok(v) => v,
        Err(_) => return default.to_vec(),
    };
    let mut out = Vec::new();
    for pair in raw.split(';') {
        let mut parts = pair.split(',');
        let a = parts.next().and_then(|s| s.trim().parse().ok());
        let b = parts.next().and_then(|s| s.trim().parse().ok());
        if let (Some(a), Some(b)) = (a, b) {
            out.push((a, b));
        }
    }
    if out.is_empty() {
        default.to_vec()
    } else {
        out
    }
}
