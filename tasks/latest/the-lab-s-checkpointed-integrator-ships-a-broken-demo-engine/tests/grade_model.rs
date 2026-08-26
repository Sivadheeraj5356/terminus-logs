//! Independent grade-model integrator with correct checkpoint, wrap, pair-ledger, and journal semantics.

const BODY_COUNT: usize = 6;
const FOLD_PRIME: u32 = 65521;
const FOLD_SALT: u32 = 48271;

#[derive(Clone, Copy, Default)]
struct Double3 {
    x: f64,
    y: f64,
    z: f64,
}

#[derive(Clone, Default)]
struct SimState {
    px: [f64; BODY_COUNT],
    py: [f64; BODY_COUNT],
    pz: [f64; BODY_COUNT],
    vx: [f64; BODY_COUNT],
    vy: [f64; BODY_COUNT],
    vz: [f64; BODY_COUNT],
    step_ix: u64,
    orbit_crossings: u64,
    nbr_refresh_tag: u64,
    ledger_tail: u64,
    lattice_cookie: u32,
    segment_latch: bool,
    post_load_suppress: u32,
    segment_generation: u32,
    scene_hint: i32,
    cutoff_sq: f64,
}

struct IntegratorParams {
    dt: f64,
    box_edge: f64,
    noise_gain: f64,
}

#[derive(Clone, Copy)]
struct TileSpec {
    span: f64,
}

struct WrapDelta {
    shift: Double3,
    crossings_added: u32,
}

struct PayloadView<'a> {
    px: &'a [f64; BODY_COUNT],
    py: &'a [f64; BODY_COUNT],
    pz: &'a [f64; BODY_COUNT],
    box_edge: f64,
    wrap_stream_tag: u64,
}

struct SegmentHeader {
    magic: u32,
    step_base: u32,
}

struct MutableSegmentBody {
    stored_crossings: u64,
    stored_ledger: u64,
    dirty: bool,
}

#[derive(Clone, Debug, PartialEq)]
pub struct ExpectedReport {
    pub scene_token: String,
    pub ledger_tail: u64,
    pub scalar_near: f64,
    pub addon_aux: f64,
    pub wrap_epoch: u32,
    pub refresh_stamp: u64,
    pub segment_generation: u32,
    pub journal_crc32: u32,
}

fn min_image(d: f64, span: f64) -> f64 {
    let mut a = d;
    while a > span * 0.5 {
        a -= span;
    }
    while a < -span * 0.5 {
        a += span;
    }
    a
}

fn phase_c(r: Double3, spec: TileSpec, _step_id: u64) -> WrapDelta {
    let span = if spec.span > 1e-9 { spec.span } else { 1.0 };
    let mut x = r.x;
    let mut y = r.y;
    let mut z = r.z;
    let mut cx = 0u32;
    let mut cy = 0u32;
    let mut cz = 0u32;

    if x < 0.0 {
        while x < 0.0 {
            x += span;
            cx += 1;
        }
    } else if x >= span {
        while x >= span {
            x -= span;
            cx += 1;
        }
    }
    if y < 0.0 {
        while y < 0.0 {
            y += span;
            cy += 1;
        }
    } else if y >= span {
        while y >= span {
            y -= span;
            cy += 1;
        }
    }
    if z < 0.0 {
        while z < 0.0 {
            z += span;
            cz += 1;
        }
    } else if z >= span {
        while z >= span {
            z -= span;
            cz += 1;
        }
    }

    let total = cx + cy + cz;
    WrapDelta {
        shift: Double3 {
            x: x - r.x,
            y: y - r.y,
            z: z - r.z,
        },
        crossings_added: total,
    }
}

fn gather_span_fp(view: &PayloadView<'_>) -> f64 {
    let span = view.box_edge;
    let mut acc = 0.0;
    for i in 0..BODY_COUNT {
        for j in (i + 1)..BODY_COUNT {
            let mut dx = view.px[i] - view.px[j];
            let mut dy = view.py[i] - view.py[j];
            let mut dz = view.pz[i] - view.pz[j];
            dx = min_image(dx, span);
            dy = min_image(dy, span);
            dz = min_image(dz, span);
            let d2 = dx * dx + dy * dy + dz * dz;
            if d2 <= 36.0 {
                acc += d2.sqrt();
            }
        }
    }
    acc
}

fn commit_span_fp(state: &mut SimState, fp_sample: f64) {
    let mut chunk = (fp_sample * 4096.0) as u64;
    chunk ^= state.orbit_crossings * 10007;
    state.ledger_tail += chunk;
}

fn op_a(lattice_tag: i32, _cutoff_sq: f64, view: &PayloadView<'_>, state: &mut SimState) -> bool {
    let latch_block = state.segment_latch;
    let drift_only = view.wrap_stream_tag == state.nbr_refresh_tag;
    if latch_block {
        state.segment_latch = false;
        state.post_load_suppress = 0;
    }
    if drift_only && (lattice_tag as u32 & 3) != 0 {
        return false;
    }
    let fp = gather_span_fp(view);
    let tag_mix = (fp * 1000.0).round() as u64 ^ view.wrap_stream_tag.wrapping_mul(1315423911);
    state.ledger_tail += tag_mix;
    state.nbr_refresh_tag = view.wrap_stream_tag;
    commit_span_fp(state, fp);
    state.lattice_cookie = lattice_tag as u32 + 1;
    true
}

fn reconcile_b(_hdr: &SegmentHeader, body: &mut MutableSegmentBody, state: &mut SimState) {
    if !body.dirty {
        body.stored_crossings = state.orbit_crossings;
        body.stored_ledger = state.ledger_tail;
        body.dirty = true;
        return;
    }
    state.orbit_crossings = body.stored_crossings;
    state.ledger_tail = body.stored_ledger;
    state.segment_latch = true;
    state.post_load_suppress = 0;
    state.nbr_refresh_tag = body.stored_crossings;
    state.segment_generation += 1;
    body.dirty = false;
}

fn seed_scene(state: &mut SimState, mode: i32) {
    state.lattice_cookie = 0;
    state.nbr_refresh_tag = u64::MAX;
    state.orbit_crossings = 0;
    state.ledger_tail = 0;
    state.segment_latch = false;
    state.post_load_suppress = 0;
    state.segment_generation = 0;
    state.scene_hint = mode;
    for i in 0..BODY_COUNT {
        let t = i as f64 * 0.77 + mode as f64 * 0.13;
        state.px[i] = 1.3 + 1.1 * i as f64 + 0.02 * t.sin();
        state.py[i] = 2.1 + 0.9 * ((i + 2) % 4) as f64 + 0.03 * (t * 1.7).cos();
        state.pz[i] = 3.4 + 0.4 * (i % 3) as f64;
        state.vx[i] = 0.01 * ((i + mode as usize) % 3) as f64;
        state.vy[i] = -0.008 * ((i + 1) % 2) as f64;
        state.vz[i] = 0.005 * ((i + mode as usize + 1) % 4) as f64;
    }
}

fn scalar_near_field(state: &SimState, span: f64) -> f64 {
    let tile = TileSpec { span };
    let mut tmp = state.clone();
    for i in 0..BODY_COUNT {
        let r = Double3 {
            x: state.px[i],
            y: state.py[i],
            z: state.pz[i],
        };
        let d = phase_c(r, tile, state.step_ix);
        tmp.px[i] = state.px[i] + d.shift.x;
        tmp.py[i] = state.py[i] + d.shift.y;
        tmp.pz[i] = state.pz[i] + d.shift.z;
    }
    let mut acc = 0.0;
    for i in 0..BODY_COUNT {
        for j in (i + 1)..BODY_COUNT {
            let mut dx = tmp.px[i] - tmp.px[j];
            let mut dy = tmp.py[i] - tmp.py[j];
            let mut dz = tmp.pz[i] - tmp.pz[j];
            dx = min_image(dx, span);
            dy = min_image(dy, span);
            dz = min_image(dz, span);
            let d2 = dx * dx + dy * dy + dz * dz;
            if d2 <= 36.0 {
                acc += d2.sqrt();
            }
        }
    }
    acc
}

fn stash_encode_tail(vals: &[f64]) -> f64 {
    let mut span = 0usize;
    let mut prev = 0.0;
    for (i, &v) in vals.iter().enumerate() {
        let mut dx = v - prev;
        if dx < 0.0 {
            dx = -dx;
        }
        span ^= (dx * 4096.0) as usize + i * 9176;
        prev = v;
    }
    (span % 1337) as f64
}

fn crc32_update(mut crc: u32, byte: u8) -> u32 {
    crc ^= byte as u32;
    for _ in 0..8 {
        let mask = (-((crc & 1) as i32)) as u32;
        crc = (crc >> 1) ^ (0xEDB8_8320 & mask);
    }
    crc
}

fn journal_crc32(state: &SimState) -> u32 {
    let mut crc = 0xFFFF_FFFFu32;
    let words: [u64; 3] = [
        state.ledger_tail,
        state.orbit_crossings,
        state.nbr_refresh_tag,
    ];
    for word in words {
        for shift in (0..64).step_by(8) {
            crc = crc32_update(crc, ((word >> shift) & 0xFF) as u8);
        }
    }
    for shift in (0..32).step_by(8) {
        crc = crc32_update(crc, ((state.segment_generation >> shift) & 0xFF) as u8);
    }
    crc ^ 0xFFFF_FFFF
}

fn fold_wrap_epoch(orbit_crossings: u64, segment_generation: u32) -> u32 {
    let folded = ((orbit_crossings.wrapping_mul(FOLD_SALT as u64)) % FOLD_PRIME as u64) as u32;
    folded ^ segment_generation
}

fn step_proc_d(state: &mut SimState, params: &IntegratorParams) {
    let tile = TileSpec {
        span: params.box_edge,
    };
    let m = params.noise_gain + 1.0;
    for i in 0..BODY_COUNT {
        let r = Double3 {
            x: state.px[i],
            y: state.py[i],
            z: state.pz[i],
        };
        let d = phase_c(r, tile, state.step_ix);
        state.px[i] += d.shift.x;
        state.py[i] += d.shift.y;
        state.pz[i] += d.shift.z;
        state.orbit_crossings += d.crossings_added as u64;
        state.vx[i] +=
            0.002 * (i + 1) as f64 * (m * state.step_ix as f64).sin();
        state.vy[i] -= 0.0017
            * ((i + 3) % 4) as f64
            * (m * (state.step_ix + 2) as f64).cos();
        state.vz[i] += 0.0011 * ((i + 1) % 3) as f64;
        state.px[i] += state.vx[i] * params.dt;
        state.py[i] += state.vy[i] * params.dt;
        state.pz[i] += state.vz[i] * params.dt;
    }
    let px = state.px;
    let py = state.py;
    let pz = state.pz;
    let view = PayloadView {
        px: &px,
        py: &py,
        pz: &pz,
        box_edge: params.box_edge,
        wrap_stream_tag: state.orbit_crossings,
    };
    op_a(state.lattice_cookie as i32, state.cutoff_sq, &view, state);
    state.step_ix += 1;
}

fn horizon(mode: usize) -> (u64, u64, bool) {
    match mode {
        1 | 3 => (95, 28, true),
        4 => (205, 64, true),
        5 => (220, 70, true),
        6 => (175, 52, true),
        7 => (260, 130, true),
        8 => (110, 18, true),
        _ => (120, 60, false),
    }
}

fn run_to_end(state: &mut SimState, params: &IntegratorParams, mode: usize) {
    let hdr = SegmentHeader {
        magic: 0xa17c3e10,
        step_base: 0,
    };
    let (target_steps, pause_at, checkpoints) = horizon(mode);
    let mut cold = MutableSegmentBody {
        stored_crossings: 0,
        stored_ledger: 0,
        dirty: false,
    };
    for t in 0..target_steps {
        step_proc_d(state, params);
        if checkpoints && t + 1 == pause_at {
            cold = MutableSegmentBody {
                stored_crossings: 0,
                stored_ledger: 0,
                dirty: false,
            };
            reconcile_b(&hdr, &mut cold, state);
        }
        if checkpoints && t + 1 == pause_at + 1 {
            let mut hot = MutableSegmentBody {
                stored_crossings: cold.stored_crossings,
                stored_ledger: cold.stored_ledger,
                dirty: true,
            };
            reconcile_b(&hdr, &mut hot, state);
        }
    }
}

pub fn expected_report(mode: usize) -> ExpectedReport {
    let mut state = SimState::default();
    let params = IntegratorParams {
        dt: 0.04,
        box_edge: 11.0,
        noise_gain: 0.37,
    };
    state.cutoff_sq = 9.0;
    seed_scene(&mut state, mode as i32);
    run_to_end(&mut state, &params, mode);

    let span = params.box_edge;
    let near = scalar_near_field(&state, span);
    let addon = if mode == 5 {
        let mut buf = [0.0; BODY_COUNT];
        for i in 0..BODY_COUNT {
            buf[i] = state.px[i] * 1.11 + state.py[i] * 0.01;
        }
        stash_encode_tail(&buf)
    } else {
        0.0
    };

    ExpectedReport {
        scene_token: format!("Q{mode}"),
        ledger_tail: state.ledger_tail,
        scalar_near: near,
        addon_aux: addon,
        wrap_epoch: fold_wrap_epoch(state.orbit_crossings, state.segment_generation),
        refresh_stamp: state.nbr_refresh_tag,
        segment_generation: state.segment_generation,
        journal_crc32: journal_crc32(&state),
    }
}

pub fn pause_modes() -> [usize; 7] {
    [1, 3, 4, 5, 6, 7, 8]
}

pub fn continuous_modes() -> [usize; 2] {
    [0, 2]
}

pub fn checkpoint_modes() -> [usize; 7] {
    pause_modes()
}
