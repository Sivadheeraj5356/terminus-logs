use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Deserialize)]
pub struct Job {
    pub id: String,
    pub dataset: String,
    pub kind: String,
    pub duration: i64,
    pub earliest_start: i64,
    pub deadline: i64,
    pub priority: i64,
    pub cpu: i64,
    pub network: i64,
    pub scratch_gb: i64,
    pub mandatory: bool,
    pub produces_restore_point: bool,
    pub restore_value: f64,
    pub replication_value: f64,
    pub optional_value: f64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Worker {
    pub id: String,
    pub cpu: i64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Dependency {
    pub before: String,
    pub after: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct DatasetTarget {
    pub dataset: String,
    pub target_time: i64,
    pub weight: f64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Config {
    pub planning_start: i64,
    pub planning_end: i64,
    pub network_capacity: i64,
    pub scratch_capacity_gb: i64,
    pub workers: Vec<Worker>,
    pub dependencies: Vec<Dependency>,
    pub conflicts: Vec<[String; 2]>,
    pub datasets: Vec<DatasetTarget>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Assignment {
    pub job: String,
    pub worker: String,
    pub start_time: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Plan {
    pub assignments: Vec<Assignment>,
}
