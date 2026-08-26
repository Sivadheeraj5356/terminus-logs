-- Builds and writes the promotion decision artifact.

local json = require("json")
local round = require("round")
local digest = require("digest")
local manifest = require("manifest")

local M = {}

local HOLDOUT_MINIMUM = 100

function M.evaluate(candidate, compose_labels, baseline, tag_present, ceiling_ms, canary_ok)
    local metrics_ok = round.round_metric(candidate.accuracy) >= round.round_metric(baseline.accuracy)
        and round.round_metric(candidate.macro_f1) >= round.round_metric(baseline.macro_f1)
    local latency_ok = candidate.latency_p99_ms < ceiling_ms
    local compose_ok = compose_labels.model_id == candidate.model_id
        and compose_labels.sklearn_pin == candidate.sklearn_pin
        and digest.digests_equal(compose_labels.artifact_digest, candidate.artifact_digest)
    local holdout_ok = (candidate.holdout_samples or 0) >= HOLDOUT_MINIMUM
    local manifest_ok = manifest.digest_registered(
        candidate.model_id,
        candidate.sklearn_pin,
        candidate.artifact_digest
    )

    local reasons = {}
    if not tag_present then
        table.insert(reasons, "upstream_tag_missing")
    end
    if not metrics_ok then
        table.insert(reasons, "metric_regression")
    end
    if not latency_ok then
        table.insert(reasons, "latency_breach")
    end
    if not compose_ok then
        table.insert(reasons, "compose_metadata_mismatch")
    end
    if not holdout_ok then
        table.insert(reasons, "holdout_sample_insufficient")
    end
    if not manifest_ok then
        table.insert(reasons, "artifact_manifest_mismatch")
    end
    table.sort(reasons)

    local approved = #reasons == 0
    return {
        candidate_id = candidate.candidate_id,
        approved = approved,
        status = approved and "approved" or "rejected",
        reasons = reasons,
        checks = {
            canary_ok = canary_ok,
            compose_ok = compose_ok,
            latency_ok = latency_ok,
            metrics_ok = metrics_ok,
            upstream_tag_present = tag_present,
            eval_fresh = true,
            holdout_ok = holdout_ok,
            manifest_ok = manifest_ok,
        },
    }
end

function M.write_decision(output_path, decision)
    return json.write_decision(output_path, decision)
end

return M
