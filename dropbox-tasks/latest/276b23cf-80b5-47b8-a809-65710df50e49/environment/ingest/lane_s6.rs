use serde_json::Value;

use crate::ingest::lab_ctx::LabCtx;
use crate::s6::s6_seal::seal_observation;

pub fn seal_report(ctx: &LabCtx, rows: &[Value]) -> String {
    seal_observation(ctx, rows)
}
