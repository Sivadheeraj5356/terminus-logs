use serde::Serialize;

#[derive(Clone, Serialize)]
pub struct TryRec {
    pub wire_tag: String,
    pub carry_at_try: u64,
    pub latch_denied: bool,
    pub key: u32,
}

#[derive(Clone, Serialize)]
pub struct CaseRec {
    pub tag: String,
    pub blk_marks: Vec<u64>,
    pub tries: Vec<TryRec>,
}

#[derive(Serialize)]
pub struct Bundle {
    pub cases: Vec<CaseRec>,
}
