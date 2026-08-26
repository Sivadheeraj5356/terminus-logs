use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Debug)]
pub struct Feature {
    pub id: String,
    pub min: i32,
    pub max: i32,
    pub cost: i32,
    pub line: usize,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Child {
    Node(String),
    Leaf(i32),
}

impl Child {
    pub fn canonical(&self) -> String {
        match self {
            Child::Node(id) => format!("N:{id}"),
            Child::Leaf(value) => format!("L:{value}"),
        }
    }
}

#[derive(Clone, Debug)]
pub struct Node {
    pub tree: String,
    pub id: String,
    pub feature: String,
    pub threshold: i32,
    pub left: Child,
    pub right: Child,
    pub line: usize,
}

#[derive(Clone, Debug)]
pub struct Tree {
    pub id: String,
    pub weight: i32,
    pub root: String,
    pub line: usize,
}

#[derive(Clone, Debug)]
pub struct Model {
    pub bias: i32,
    pub features: BTreeMap<String, Feature>,
    pub trees: BTreeMap<String, Tree>,
    pub nodes: BTreeMap<(String, String), Node>,
}

#[derive(Clone, Debug)]
pub struct CheckState {
    pub session: String,
    pub check: String,
    pub budget: i32,
    pub point: BTreeMap<String, i32>,
    pub locked: BTreeSet<String>,
}

#[derive(Clone, Debug)]
pub struct Vote {
    pub tree: String,
    pub leaf: i32,
    pub vote: i32,
}

#[derive(Clone, Debug)]
pub struct Evaluation {
    pub score: i32,
    pub prediction: &'static str,
    pub votes: Vec<Vote>,
}

#[derive(Clone, Debug)]
pub struct Counterexample {
    pub cost: i32,
    pub changed: usize,
    pub values: BTreeMap<String, i32>,
    pub evaluation: Evaluation,
}

#[derive(Clone, Debug)]
pub struct CheckResult {
    pub state: CheckState,
    pub base: Evaluation,
    pub counterexample: Option<Counterexample>,
}

#[derive(Clone, Debug)]
pub struct ContractError {
    pub token: &'static str,
    pub line: usize,
}

impl ContractError {
    pub fn diagnostic(&self) -> String {
        format!("{}:{}", self.token, self.line)
    }
}
