use crate::interp::linear_at;

pub const T0: f64 = 20.0;
pub const H0: f64 = 50.0;
pub const BETA: f64 = 0.012;

pub const ALPHA: [f64; 4] = [0.0021, 0.0018, 0.0024, 0.0010];

#[derive(Clone, Debug)]
pub struct RowPt {
    pub pos: f64,
    pub cyan: f64,
    pub magenta: f64,
    pub yellow: f64,
    pub silver: f64,
}

#[derive(Clone, Debug)]
pub struct ChannelBlock {
    pub cyan: f64,
    pub magenta: f64,
    pub yellow: f64,
    pub silver: f64,
}

impl ChannelBlock {
    pub fn from_arr(v: [f64; 4]) -> Self {
        Self {
            cyan: v[0],
            magenta: v[1],
            yellow: v[2],
            silver: v[3],
        }
    }
}

fn apply_climate_block(temp_c: f64, rh_pct: f64, raw: [f64; 4]) -> [f64; 4] {
    let mut out = [0.0; 4];
    for i in 0..4 {
        let scale = (ALPHA[i] * (temp_c - T0)).exp() * (1.0 + BETA * (rh_pct - H0) / 100.0);
        out[i] = raw[i] * scale;
    }
    out
}

fn ordered_samples(samples: &[RowPt]) -> Vec<RowPt> {
    let mut ordered = samples.to_vec();
    ordered.sort_by(|a, b| a.pos.partial_cmp(&b.pos).unwrap_or(std::cmp::Ordering::Equal));
    let mut dedup: Vec<RowPt> = Vec::new();
    for s in ordered {
        if let Some(last) = dedup.last_mut() {
            if (last.pos - s.pos).abs() < 1e-12 {
                *last = s;
                continue;
            }
        }
        dedup.push(s);
    }
    dedup
}

pub fn step_rho(temp_c: f64, rh_pct: f64, samples: &[RowPt]) -> (ChannelBlock, ChannelBlock, ChannelBlock) {
    let ordered = ordered_samples(samples);
    let corrected: Vec<RowPt> = ordered
        .iter()
        .map(|s| {
            let raw = [s.cyan, s.magenta, s.yellow, s.silver];
            let c = apply_climate_block(temp_c, rh_pct, raw);
            RowPt {
                pos: s.pos,
                cyan: c[0],
                magenta: c[1],
                yellow: c[2],
                silver: c[3],
            }
        })
        .collect();
    let start = linear_at(&corrected, 0.0);
    let end = linear_at(&corrected, 1.0);
    let mid_raw = {
        let mut sums = [0.0; 4];
        let mut n = 0usize;
        for s in &corrected {
            if s.pos >= 0.40 && s.pos <= 0.60 {
                sums[0] += s.cyan;
                sums[1] += s.magenta;
                sums[2] += s.yellow;
                sums[3] += s.silver;
                n += 1;
            }
        }
        if n == 0 {
            for s in &corrected {
                sums[0] += s.cyan;
                sums[1] += s.magenta;
                sums[2] += s.yellow;
                sums[3] += s.silver;
                n += 1;
            }
        }
        let nf = n as f64;
        [sums[0] / nf, sums[1] / nf, sums[2] / nf, sums[3] / nf]
    };
    (
        ChannelBlock::from_arr(start),
        ChannelBlock::from_arr(end),
        ChannelBlock::from_arr(mid_raw),
    )
}
