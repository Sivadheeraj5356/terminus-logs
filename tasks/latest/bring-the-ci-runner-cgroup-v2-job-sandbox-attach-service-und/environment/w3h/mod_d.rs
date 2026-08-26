mod hash_help;

#[derive(Clone, Debug)]
pub struct TargetRow {
    pub arm_key: String,
    pub pack_bits: u64,
    pub latch_val: u32,
    pub base_v: f64,
    pub held_flag: bool,
    pub gate_first: bool,
}

#[derive(Clone, Debug)]
pub struct SeedBundle {
    pub pin: i32,
    pub lane_count: i32,
    pub bin_seed: u64,
}

#[derive(Clone, Debug)]
pub struct StampWitness {
    pub fold_seed: u64,
    pub coherent: bool,
}

#[derive(Clone, Debug)]
pub struct EmittedRow {
    pub arm_key: String,
    pub vec_core: Vec<String>,
    pub bag_a: Vec<i32>,
    pub bag_b: Vec<i32>,
    pub mag: f64,
    pub lane_n: i32,
    pub emit_hx: String,
    pub held: f64,
    pub band_lo: f64,
    pub band_hi: f64,
    pub res_delta: f64,
}

fn slot_vec(pack_bits: u64) -> Vec<i32> {
    let mut bag = Vec::with_capacity(4);
    for i in 0..4 {
        bag.push(((pack_bits >> (i * 8)) & 0xff) as i32);
    }
    bag
}

fn fold_key(key: &str) -> u64 {
    let mut h: u64 = 0xcbf2_9ce4_8422_2325;
    for b in key.as_bytes() {
        h ^= u64::from(*b);
        h = h.wrapping_mul(0x0100_0000_01b3);
    }
    h
}

pub fn fold_z1(targets: &[TargetRow], seeds: &SeedBundle, _witness: &StampWitness) -> Vec<EmittedRow> {
    let mut out = Vec::new();
    for t in targets {
        if t.held_flag {
            continue;
        }
        let hx = t.pack_bits ^ u64::from(t.latch_val);
        let emit_hx = format!("{hx:016x}");
        let bag_a = slot_vec(t.pack_bits);
        let bag_b: Vec<i32> = bag_a.iter().map(|v| (v + 1) & 0xff).collect();
        let vec_core: Vec<String> = bag_a.iter().map(|v| format!("{v:02x}")).collect();
        let res = ((t.pack_bits & 0xffff) as f64) / 65536.0 - t.base_v;
        out.push(EmittedRow {
            arm_key: t.arm_key.clone(),
            vec_core,
            bag_a,
            bag_b,
            mag: res.abs(),
            lane_n: seeds.lane_count,
            emit_hx,
            held: 0.0,
            band_lo: -1.0,
            band_hi: 1.0,
            res_delta: res,
        });
    }
    out
}
