use serde_json::Value;

use crate::ingest::lane_n7::bind_observation_seal;

pub fn seal_observation(_ctx: &crate::ingest::lab_ctx::LabCtx, rows: &[Value]) -> String {
    bind_observation_seal(rows)
}
