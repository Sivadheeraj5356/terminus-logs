use super::lane::lane_p;

#[derive(Clone, Debug)]
pub struct LaneItem {
    pub job: u32,
    pub slot: u64,
    pub draws: Vec<f64>,
}

#[derive(Clone, Debug, Default)]
pub struct PendingLane {
    pub items: Vec<LaneItem>,
}

impl PendingLane {
    pub fn admit(&mut self, job: u32, base: u64, plan_tag: u32, draws: &[f64]) -> u64 {
        let slot = lane_p(job, base, plan_tag);
        self.items.push(LaneItem {
            job,
            slot,
            draws: draws.to_vec(),
        });
        slot
    }

    pub fn open_jobs(&self) -> Vec<i32> {
        let mut jobs: Vec<i32> = self.items.iter().map(|item| item.job as i32).collect();
        jobs.sort_unstable();
        jobs
    }
}
