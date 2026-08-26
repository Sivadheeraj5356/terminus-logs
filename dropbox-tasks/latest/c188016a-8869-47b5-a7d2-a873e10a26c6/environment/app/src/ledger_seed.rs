#[allow(dead_code)]
pub struct BreakglassEvidence {
    pub principals: &'static str,
    pub resources: &'static str,
    pub tickets: &'static str,
    pub approvers: &'static str,
    pub requests: &'static str,
    pub approvals: &'static str,
    pub events: &'static str,
    pub revocations: &'static str,
}

pub fn default_evidence_names() -> BreakglassEvidence {
    BreakglassEvidence {
        principals: "principals.tsv",
        resources: "resources.tsv",
        tickets: "tickets.tsv",
        approvers: "approvers.tsv",
        requests: "requests.tsv",
        approvals: "approvals.tsv",
        events: "events.tsv",
        revocations: "revocations.tsv",
    }
}
