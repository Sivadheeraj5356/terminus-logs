use std::collections::BTreeMap;

#[derive(Clone, Debug)]
pub struct Entry {
    pub label: String,
    pub raw: String,
    pub unit: String,
    pub lo: i32,
    pub hi: i32,
    pub orient: i32,
    pub weight: i32,
}

#[derive(Clone, Debug, Default)]
pub struct Registry {
    pub aliases: BTreeMap<String, String>,
}

#[derive(Clone, Debug, Eq, Ord, PartialEq, PartialOrd)]
pub struct SpanKey {
    pub unit: String,
    pub lo: i32,
    pub hi: i32,
}

impl SpanKey {
    pub fn text(&self) -> String {
        format!("{}:{}-{}", self.unit, self.lo, self.hi)
    }
}

#[derive(Clone, Debug)]
pub struct Leaf {
    pub label: String,
    pub key: SpanKey,
    pub weight: i32,
}

#[derive(Clone, Debug)]
pub struct Geometry {
    pub limit: i32,
}

#[derive(Clone, Debug)]
pub struct StateA {
    pub keys: Vec<String>,
    pub score: i32,
    pub ready: bool,
    pub labels: Vec<String>,
}

#[derive(Clone, Debug)]
pub struct InputsB {
    pub request_id: String,
    pub base: String,
    pub revision: String,
}

#[derive(Clone, Debug)]
pub struct ScopeC {
    pub parts: Vec<String>,
}

#[derive(Clone, Debug)]
pub struct Stamp {
    pub value: String,
}

#[derive(Clone, Debug)]
pub struct Snapshot {
    pub token: String,
    pub state: StateA,
    pub request_id: String,
}

#[derive(Clone, Debug)]
pub struct BookE {
    pub latest: Option<Snapshot>,
    pub parts: Vec<String>,
}

#[derive(Clone, Debug)]
pub struct FrameD {
    pub token: String,
    pub state: StateA,
    pub request_id: String,
    pub parts: Vec<String>,
}

#[derive(Clone, Debug)]
pub struct ScoresF {
    pub score: i32,
    pub ready: bool,
}

#[derive(Clone, Debug)]
pub struct Request {
    pub meta: InputsB,
    pub scope: ScopeC,
    pub registry: Registry,
    pub entries: Vec<Entry>,
    pub geometry: Geometry,
    pub replay_latest: bool,
    pub state_dir: String,
}
