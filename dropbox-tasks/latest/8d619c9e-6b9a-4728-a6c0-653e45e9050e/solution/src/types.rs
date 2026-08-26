#[derive(Clone)]
pub struct TrayCfg {
    pub capacity_units: i64,
    pub tier: i64,
    pub regen_every: i64,
}

#[derive(Clone, Default)]
pub struct TrayState {
    pub name: String,
    pub capacity_units: i64,
    pub tier: i64,
    pub regen_every: i64,
    pub units: i64,
    pub sealed: bool,
    pub locked: bool,
    pub held: bool,
    pub cycles_since_regen: i64,
}

pub struct ParsedLine {
    pub event_id: String,
    pub op: String,
    pub tray_id: String,
    pub units_raw: String,
    pub lot_raw: String,
}

pub struct ReplayResult {
    pub trays: std::collections::BTreeMap<String, TrayState>,
    pub tray_cfg: std::collections::HashMap<String, TrayCfg>,
    pub rejected: Vec<(usize, String, String, String, usize)>,
    pub duplicates: Vec<(usize, String, String)>,
    pub invalid: Vec<usize>,
    pub total_lines: usize,
    pub applied: usize,
    pub loads_applied: i64,
    pub unloads_applied: i64,
}
