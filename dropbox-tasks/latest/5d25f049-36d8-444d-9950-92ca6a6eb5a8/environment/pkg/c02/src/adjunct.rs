use indexmap::IndexMap;
use hx01::model::{PolicyIntent, RuntimeOverrides, RuleAction, RuleSpec};
use hx01::Result;

pub fn apply_runtime_adjuncts(intent: PolicyIntent, overrides: &RuntimeOverrides) -> Result<PolicyIntent> {
    let mut out = intent;
    for (rule_id, ov) in &overrides.rules {
        for tenant in out.tenants.values_mut() {
            if let Some(rule) = tenant.rules.get_mut(rule_id) {
                if ov.tenant.is_some() {
                    rule.tenant = ov.tenant.clone().unwrap();
                }
                if ov.ownership_scope.is_some() {
                    rule.tenant = ov.ownership_scope.clone().unwrap();
                }
                if let Some(action) = &ov.action {
                    rule.action = action.clone();
                }
            }
        }
    }
    Ok(out)
}
