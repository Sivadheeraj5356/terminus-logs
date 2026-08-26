#[derive(Clone, Debug)]
pub struct Peak { pub id: String, pub q: i64, pub tol: i64, pub weight: i64 }
#[derive(Clone, Debug)]
pub struct Scan { pub name: String, pub peaks: Vec<Peak> }
#[derive(Clone, Debug)]
pub struct Study {
    pub hmax: i32, pub scan_lo: i64, pub scan_hi: i64,
    pub scale_min: i64, pub scale_max: i64, pub drift: i64,
    pub shift_min: i64, pub shift_max: i64,
    pub max_impurities: usize, pub max_missing: usize, pub min_consensus: usize,
    pub phases: Vec<char>, pub scans: Vec<Scan>,
}
#[derive(Clone, Debug)]
pub struct Shell { pub n: i32, pub h: i32, pub k: i32, pub l: i32 }
#[derive(Clone, Debug)]
pub struct ScanPlan { pub assign: Vec<i32>, pub missing: Vec<i32>, pub residual: i64, pub weight: i64 }
#[derive(Clone, Debug)]
pub struct Objective { pub indexed_weight: i64, pub consensus: usize, pub residual: i64, pub missing: usize, pub orphans: usize, pub motion: i64 }
#[derive(Clone, Debug)]
pub struct Plan { pub phase: char, pub a: [i64;2], pub z: [i64;2], pub scans: [ScanPlan;2], pub objective: Objective, pub optimal_count: i64, pub shells: Vec<Shell> }
