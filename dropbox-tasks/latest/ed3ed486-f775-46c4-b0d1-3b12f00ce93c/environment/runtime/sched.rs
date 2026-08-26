use serde::Deserialize;
use std::collections::HashMap;
use std::fs;
use std::path::Path;

#[derive(Clone, Debug, Deserialize)]
pub struct BatchEntry {
    pub slot: u32,
    pub values: Vec<f32>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct TrainingPlan {
    pub version: u32,
    pub gauge_ceiling: f64,
    pub snapshot_step: Option<u32>,
    #[serde(default)]
    pub continue_snapshot_step: Option<u32>,
    #[serde(default)]
    pub snapshot_after_admits: Option<u32>,
    pub batch: Vec<BatchEntry>,
    #[serde(default)]
    pub slots: Vec<u32>,
}

impl TrainingPlan {
    pub fn load(path: &Path) -> Result<Self, String> {
        let body = fs::read_to_string(path).map_err(|e| e.to_string())?;
        let mut plan: TrainingPlan = toml::from_str(&body).map_err(|e| e.to_string())?;
        if plan.slots.is_empty() {
            plan.slots = plan.batch.iter().map(|entry| entry.slot).collect();
        }
        Ok(plan)
    }

    pub fn payload_for_slot(&self, slot: u32) -> Vec<f32> {
        let map: HashMap<u32, Vec<f32>> = self
            .batch
            .iter()
            .map(|entry| (entry.slot, entry.values.clone()))
            .collect();
        map.get(&slot).cloned().unwrap_or_default()
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
    slots: Vec<u32>,
    mode: RunMode,
    seed: u64,
    accum_steps: usize,
}

impl SchedulePlan {
    pub fn from_plan(plan: &TrainingPlan, mode: RunMode, seed: u64, accum_steps: usize) -> Self {
        Self {
            slots: plan.slots.clone(),
            mode,
            seed,
            accum_steps,
        }
    }

    pub fn waves(&self) -> Vec<Vec<u32>> {
        self.build_waves(0, 0)
    }

    pub fn waves_from(&self, start_step: u32) -> Vec<Vec<u32>> {
        self.build_waves(start_step, 0)
    }

    pub fn waves_from_offset(&self, start_step: u32, wave_offset: u32) -> Vec<Vec<u32>> {
        self.build_waves(start_step, wave_offset)
    }

    fn build_waves(&self, start_step: u32, wave_offset: u32) -> Vec<Vec<u32>> {
        let accum = self.accum_steps;
        let step_count = self.slots.len() / accum;
        let mut waves = Vec::new();
        for step in start_step as usize..step_count {
            let begin = step * accum;
            let end = begin + accum;
            let mut wave: Vec<u32> = self.slots[begin..end].to_vec();
            if self.mode == RunMode::Concurrent {
                permute_in_place(&mut wave, self.seed.wrapping_add(step as u64));
            }
            if step == start_step as usize && wave_offset > 0 {
                let skip = wave_offset.min(wave.len() as u32) as usize;
                wave = wave.split_off(skip);
            }
            if !wave.is_empty() {
                waves.push(wave);
            }
        }
        waves
    }
}

fn permute_in_place(items: &mut [u32], seed: u64) {
    let mut state = seed;
    for i in (1..items.len()).rev() {
        state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
        let j = (state as usize) % (i + 1);
        items.swap(i, j);
    }
}
