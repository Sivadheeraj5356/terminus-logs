use crate::types::{Assignment, Config, Job, Plan};

pub fn build(jobs: &[Job], config: &Config) -> Plan {
    // Deliberately simple baseline: it is feasible on easy inputs but leaves
    // substantial score on the table for the task solver to recover.
    let mut assignments = Vec::new();
    if config.workers.is_empty() {
        return Plan { assignments };
    }
    let worker = &config.workers[0].id;
    let mut t = config.planning_start;
    for job in jobs.iter().filter(|j| j.mandatory) {
        t = t.max(job.earliest_start);
        assignments.push(Assignment { job: job.id.clone(), worker: worker.clone(), start_time: t });
        t += job.duration;
    }
    Plan { assignments }
}
