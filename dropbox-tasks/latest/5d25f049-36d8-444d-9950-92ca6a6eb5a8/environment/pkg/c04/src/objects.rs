use hx01::model::{Annotation, BackendRule, BackendState};

pub fn is_managed(rule: &BackendRule) -> bool {
    rule.annotation.as_ref().map(|a| a.managed).unwrap_or(false)
}

pub fn is_foreign(rule: &BackendRule) -> bool {
    !is_managed(rule)
}

pub fn annotation_for(
    logical_id: &str,
    generation: u64,
    phase: &str,
    tenant: &str,
    counter_lineage: Option<String>,
) -> Annotation {
    Annotation {
        managed: true,
        logical_id: hx01::LogicalId::new(logical_id),
        generation,
        phase: phase.to_string(),
        tenant: tenant.to_string(),
        counter_lineage,
    }
}

pub fn referenced_handles(state: &BackendState) -> Vec<u64> {
    let mut out = Vec::new();
    for handles in state.chains.values() {
        out.extend(handles.iter().copied());
    }
    out.sort();
    out.dedup();
    out
}
