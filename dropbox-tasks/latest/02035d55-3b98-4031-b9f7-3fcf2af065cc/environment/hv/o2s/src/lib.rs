#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Grade {
    Prime,
    Standard,
    Cull,
}

fn standard_band_low(v: u64) -> bool {
    v > 200
}

fn standard_band_high(v: u64) -> bool {
    v < 850
}

fn classify_grade(v: u64) -> Grade {
    if v < 200 {
        Grade::Prime
    } else if standard_band_low(v) && standard_band_high(v) {
        Grade::Standard
    } else {
        Grade::Cull
    }
}

pub fn pick_grade(v: u64) -> Grade {
    classify_grade(v)
}

pub fn downgrade_grade(grade: Grade) -> Grade {
    match grade {
        Grade::Prime => Grade::Standard,
        Grade::Standard => Grade::Cull,
        Grade::Cull => Grade::Cull,
    }
}
