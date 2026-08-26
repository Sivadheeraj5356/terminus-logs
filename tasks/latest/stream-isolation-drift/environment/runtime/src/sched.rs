use serde::Deserialize;
use std::collections::HashMap;
use std::fs;
use std::path::Path;

#[derive(Clone, Debug, Deserialize)]
pub struct JobEntry {
    pub job: u32,
    pub draws: Vec<f64>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct JobPlan {
    pub version: u32,
    pub gauge_ceiling: f64,
    pub window: usize,
    pub checkpoint_pass: Option<u32>,
    #[serde(default)]
    pub continue_checkpoint_pass: Option<u32>,
    pub jobs: Vec<JobEntry>,
    #[serde(default)]
    pub job_order: Vec<u32>,
}

impl JobPlan {
    pub fn load(path: &Path) -> Result<Self, String> {
        let body = fs::read_to_string(path).map_err(|e| e.to_string())?;
        let mut plan: JobPlan = toml::from_str(&body).map_err(|e| e.to_string())?;
        if plan.job_order.is_empty() {
            plan.job_order = plan.jobs.iter().map(|entry| entry.job).collect();
        }
        Ok(plan)
    }

    pub fn draws_for_job(&self, job: u32) -> Vec<f64> {
        let map: HashMap<u32, Vec<f64>> = self
            .jobs
            .iter()
            .map(|entry| (entry.job, entry.draws.clone()))
            .collect();
        map.get(&job).cloned().unwrap_or_default()
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RunMode {
    Serial,
    Concurrent,
}

impl RunMode {
    pub fn parse(raw: &str) -> Result<Self, String> {
        match raw {
            "serial" => Ok(RunMode::Serial),
            "parallel" => Ok(RunMode::Concurrent),
            other => Err(format!("unknown mode: {other}")),
        }
    }

    pub fn as_str(self) -> &'static str {
        match self {
            RunMode::Serial => "serial",
            RunMode::Concurrent => "parallel",
        }
    }
}

pub struct SchedulePlan {
    jobs: Vec<u32>,
    mode: RunMode,
    mix: u64,
    window: usize,
}

impl SchedulePlan {
    pub fn from_plan(plan: &JobPlan, mode: RunMode, mix: u64) -> Self {
        Self {
            jobs: plan.job_order.clone(),
            mode,
            mix,
            window: plan.window,
        }
    }

    pub fn waves(&self) -> Vec<Vec<u32>> {
        self.build_waves(0)
    }

    pub fn waves_from(&self, start_pass: u32) -> Vec<Vec<u32>> {
        self.build_waves(start_pass)
    }

    fn build_waves(&self, start_pass: u32) -> Vec<Vec<u32>> {
        let window = self.window;
        let pass_count = self.jobs.len() / window;
        let mut waves = Vec::new();
        for pass in start_pass as usize..pass_count {
            let begin = pass * window;
            let end = begin + window;
            let mut wave: Vec<u32> = self.jobs[begin..end].to_vec();
            if self.mode == RunMode::Concurrent {
                permute_in_place(&mut wave, self.mix.wrapping_add(pass as u64));
            }
            waves.push(wave);
        }
        waves
    }
}

fn permute_in_place(items: &mut [u32], mix: u64) {
    let mut state = mix;
    for i in (1..items.len()).rev() {
        state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
        let j = (state as usize) % (i + 1);
        items.swap(i, j);
    }
}
