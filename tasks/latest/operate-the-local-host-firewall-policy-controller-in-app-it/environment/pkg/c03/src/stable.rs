use hx01::ids::ObjectKind;
use hx01::model::{CompiledIntent, CompiledObject, PolicyIntent};
use hx01::Result;
use sha2::{Digest, Sha256};

use crate::names::visible_name;
use crate::rules::rule_revision;

/// Compile policy intent into backend objects.
pub fn compile_intent(intent: &PolicyIntent) -> Result<CompiledIntent> {
    let mut objects = Vec::new();
    let mut chain_order = Vec::new();
    for (tenant_name, tenant) in &intent.tenants {
        for (set_id, set) in &tenant.sets {
            let rev = format!("{:x}", Sha256::digest(serde_json::to_string(set)?.as_bytes()));
            objects.push(CompiledObject {
                visible_name: visible_name("set", set_id, &rev),
                logical_id: set.id.clone(),
                kind: ObjectKind::Set,
                semantic_revision: rev,
                payload: serde_json::to_value(set)?,
            });
        }
        for (chain_id, chain) in &tenant.chains {
            chain_order.push(chain.id.clone());
            let rev = format!("{:x}", Sha256::digest(serde_json::to_string(chain)?.as_bytes()));
            objects.push(CompiledObject {
                visible_name: visible_name("chain", chain_id, &rev),
                logical_id: chain.id.clone(),
                kind: ObjectKind::Chain,
                semantic_revision: rev,
                payload: serde_json::to_value(chain)?,
            });
        }
        for (rule_id, rule) in &tenant.rules {
            let rev = rule_revision(rule);
            objects.push(CompiledObject {
                visible_name: visible_name("rule", rule_id, &rev),
                logical_id: rule.id.clone(),
                kind: ObjectKind::Rule,
                semantic_revision: rev,
                payload: serde_json::to_value(rule)?,
            });
        }
        let _ = tenant_name;
    }
    let digest = canonical_digest(&objects);
    Ok(CompiledIntent {
        objects,
        canonical_digest: digest,
        input_chain_order: chain_order,
    })
}

pub fn canonical_digest(objects: &[CompiledObject]) -> String {
    let mut parts: Vec<String> = objects
        .iter()
        .map(|o| format!("{}:{}:{}", o.logical_id.0, format!("{:?}", o.kind), o.semantic_revision))
        .collect();
    parts.sort();
    format!("{:x}", Sha256::digest(parts.join("|").as_bytes()))
}

pub fn canonicalize_objects(objects: &mut [CompiledObject]) {
    let set_idxs: Vec<usize> = objects
        .iter()
        .enumerate()
        .filter(|(_, o)| o.kind == ObjectKind::Set)
        .map(|(i, _)| i)
        .collect();
    let mut set_keys: Vec<(String, usize)> = set_idxs
        .into_iter()
        .map(|i| (objects[i].logical_id.0.clone(), i))
        .collect();
    set_keys.sort_by(|a, b| a.0.cmp(&b.0));
    // reorder only set objects in-place by stable swap logic
    let mut sorted_sets = Vec::new();
    for (_, idx) in &set_keys {
        sorted_sets.push(objects[*idx].clone());
    }
    let mut si = 0;
    for obj in objects.iter_mut() {
        if obj.kind == ObjectKind::Set {
            *obj = sorted_sets[si].clone();
            si += 1;
        }
    }
}
