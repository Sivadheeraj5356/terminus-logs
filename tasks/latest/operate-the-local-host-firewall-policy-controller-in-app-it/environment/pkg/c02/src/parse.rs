use std::path::Path;

use indexmap::IndexMap;
use hx01::model::{PolicyIntent, TenantIntent};
use hx01::{PolicyError, Result};
use serde::Deserialize;

#[derive(Debug, Deserialize)]
struct RootDoc {
    #[serde(default)]
    priority: i32,
    #[serde(default)]
    tenant: String,
    #[serde(default)]
    sets: IndexMap<String, SetDoc>,
    #[serde(default)]
    rules: IndexMap<String, RuleDoc>,
}

#[derive(Debug, Deserialize)]
struct SetDoc {
    #[serde(default)]
    tenant: String,
    members: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct RuleDoc {
    #[serde(default)]
    tenant: String,
    action: String,
    #[serde(default)]
    src_set: Option<String>,
    #[serde(default)]
    dst_set: Option<String>,
    #[serde(default)]
    dst_port: Option<u16>,
    #[serde(default)]
    ordered_index: usize,
}

pub fn load_base(path: &Path) -> Result<(PolicyIntent, i32)> {
    let text = std::fs::read_to_string(path)?;
    let doc: RootDoc = toml::from_str(&text).map_err(|e| PolicyError::Config(e.to_string()))?;
    Ok((doc_to_intent(&doc), doc.priority))
}

pub fn load_dropin(path: &Path) -> Result<(PolicyIntent, i32, String)> {
    let text = std::fs::read_to_string(path)?;
    let doc: RootDoc = toml::from_str(&text).map_err(|e| PolicyError::Config(e.to_string()))?;
    let normalized = path
        .canonicalize()
        .unwrap_or_else(|_| path.to_path_buf())
        .display()
        .to_string();
    Ok((doc_to_intent(&doc), doc.priority, normalized))
}

fn doc_to_intent(doc: &RootDoc) -> PolicyIntent {
    let mut tenants = IndexMap::new();
    let tenant_name = if doc.tenant.is_empty() {
        "default".to_string()
    } else {
        doc.tenant.clone()
    };
    let mut tenant = TenantIntent {
        sets: IndexMap::new(),
        chains: IndexMap::new(),
        rules: IndexMap::new(),
    };
    for (id, set) in &doc.sets {
        let t = if set.tenant.is_empty() {
            tenant_name.clone()
        } else {
            set.tenant.clone()
        };
        tenant.sets.insert(
            id.clone(),
            hx01::model::AddressSet {
                id: hx01::LogicalId::new(id),
                tenant: t,
                members: set.members.clone(),
            },
        );
    }
    let mut ordered_rules = Vec::new();
    for (id, rule) in &doc.rules {
        let t = if rule.tenant.is_empty() {
            tenant_name.clone()
        } else {
            rule.tenant.clone()
        };
        let action = match rule.action.as_str() {
            "allow" => hx01::model::RuleAction::Allow,
            "drop" => hx01::model::RuleAction::Drop,
            "log" => hx01::model::RuleAction::Log,
            other => hx01::model::RuleAction::Drop,
        };
        tenant.rules.insert(
            id.clone(),
            hx01::model::RuleSpec {
                id: hx01::LogicalId::new(id),
                tenant: t,
                action,
                src_set: rule.src_set.as_ref().map(|s| hx01::LogicalId::new(s)),
                dst_set: rule.dst_set.as_ref().map(|s| hx01::LogicalId::new(s)),
                dst_port: rule.dst_port,
                ordered_index: rule.ordered_index,
            },
        );
        ordered_rules.push((rule.ordered_index, id.clone()));
    }
    ordered_rules.sort_by_key(|(idx, _)| *idx);
    let chain_id = hx01::LogicalId::new("ingress");
    tenant.chains.insert(
        "ingress".into(),
        hx01::model::ChainSpec {
            id: chain_id,
            tenant: tenant_name.clone(),
            rules: ordered_rules.into_iter().map(|(_, id)| hx01::LogicalId::new(id)).collect(),
        },
    );
    tenants.insert(tenant_name, tenant);
    PolicyIntent { tenants }
}
