use crate::types::{Child, ContractError, Feature, Model, Node, Tree};
use crate::util::{hash_hex, parse_canonical_i32, valid_identifier};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone)]
struct Violation {
    priority: u8,
    line: usize,
    token: &'static str,
}

fn push(v: &mut Vec<Violation>, priority: u8, line: usize, token: &'static str) {
    v.push(Violation { priority, line, token });
}

fn child(value: &str) -> Option<Child> {
    if let Some(id) = value.strip_prefix("N:") {
        valid_identifier(id).then(|| Child::Node(id.to_string()))
    } else if value == "L:-1" {
        Some(Child::Leaf(-1))
    } else if value == "L:1" {
        Some(Child::Leaf(1))
    } else {
        None
    }
}

pub fn parse_model(text: &str) -> Result<Model, ContractError> {
    let mut violations = Vec::new();
    let mut seen_header = false;
    let mut first_record = true;
    let mut bias: Option<(i32, usize)> = None;
    let mut features = BTreeMap::<String, Feature>::new();
    let mut trees = BTreeMap::<String, Tree>::new();
    let mut nodes = BTreeMap::<(String, String), Node>::new();
    let mut feature_lines = BTreeMap::<String, usize>::new();
    let mut tree_lines = BTreeMap::<String, usize>::new();
    let mut node_lines = BTreeMap::<(String, String), usize>::new();
    let mut non_comment = 0usize;

    for (index, raw) in text.lines().enumerate() {
        let line = index + 1;
        if raw.is_empty() || raw.starts_with('#') {
            continue;
        }
        non_comment += 1;
        let fields: Vec<&str> = raw.split('|').collect();
        let kind = fields[0];
        if first_record {
            first_record = false;
            if fields.as_slice() != ["MODEL", "1"] {
                push(&mut violations, 1, line, "E_MODEL_HEADER");
            } else {
                seen_header = true;
                continue;
            }
        } else if kind == "MODEL" {
            push(&mut violations, 1, line, "E_MODEL_HEADER");
            continue;
        }

        match kind {
            "BIAS" => {
                if fields.len() != 2 {
                    push(&mut violations, 2, line, "E_MODEL_FIELDS");
                    continue;
                }
                let Some(value) = parse_canonical_i32(fields[1]) else {
                    push(&mut violations, 4, line, "E_MODEL_NUMBER");
                    continue;
                };
                if bias.is_some() {
                    push(&mut violations, 5, line, "E_MODEL_DUPLICATE");
                } else {
                    bias = Some((value, line));
                }
                if !(-100..=100).contains(&value) {
                    push(&mut violations, 6, line, "E_MODEL_RANGE");
                }
            }
            "FEATURE" => {
                if fields.len() != 5 {
                    push(&mut violations, 2, line, "E_MODEL_FIELDS");
                    continue;
                }
                if !valid_identifier(fields[1]) {
                    push(&mut violations, 3, line, "E_MODEL_IDENTIFIER");
                    continue;
                }
                let parsed = (
                    parse_canonical_i32(fields[2]),
                    parse_canonical_i32(fields[3]),
                    parse_canonical_i32(fields[4]),
                );
                let (Some(min), Some(max), Some(cost)) = parsed else {
                    push(&mut violations, 4, line, "E_MODEL_NUMBER");
                    continue;
                };
                let id = fields[1].to_string();
                if feature_lines.insert(id.clone(), line).is_some() {
                    push(&mut violations, 5, line, "E_MODEL_DUPLICATE");
                    continue;
                }
                if min > max || max.saturating_sub(min) > 6 || !(1..=9).contains(&cost) {
                    push(&mut violations, 6, line, "E_MODEL_RANGE");
                }
                features.insert(id.clone(), Feature { id, min, max, cost, line });
            }
            "TREE" => {
                if fields.len() != 4 {
                    push(&mut violations, 2, line, "E_MODEL_FIELDS");
                    continue;
                }
                if !valid_identifier(fields[1]) || !valid_identifier(fields[3]) {
                    push(&mut violations, 3, line, "E_MODEL_IDENTIFIER");
                    continue;
                }
                let Some(weight) = parse_canonical_i32(fields[2]) else {
                    push(&mut violations, 4, line, "E_MODEL_NUMBER");
                    continue;
                };
                let id = fields[1].to_string();
                if tree_lines.insert(id.clone(), line).is_some() {
                    push(&mut violations, 5, line, "E_MODEL_DUPLICATE");
                    continue;
                }
                if !(1..=20).contains(&weight) {
                    push(&mut violations, 6, line, "E_MODEL_RANGE");
                }
                trees.insert(id.clone(), Tree { id, weight, root: fields[3].to_string(), line });
            }
            "NODE" => {
                if fields.len() != 7 {
                    push(&mut violations, 2, line, "E_MODEL_FIELDS");
                    continue;
                }
                if !valid_identifier(fields[1])
                    || !valid_identifier(fields[2])
                    || !valid_identifier(fields[3])
                {
                    push(&mut violations, 3, line, "E_MODEL_IDENTIFIER");
                    continue;
                }
                let Some(threshold) = parse_canonical_i32(fields[4]) else {
                    push(&mut violations, 4, line, "E_MODEL_NUMBER");
                    continue;
                };
                let Some(left) = child(fields[5]) else {
                    push(&mut violations, 2, line, "E_MODEL_FIELDS");
                    continue;
                };
                let Some(right) = child(fields[6]) else {
                    push(&mut violations, 2, line, "E_MODEL_FIELDS");
                    continue;
                };
                let key = (fields[1].to_string(), fields[2].to_string());
                if node_lines.insert(key.clone(), line).is_some() {
                    push(&mut violations, 5, line, "E_MODEL_DUPLICATE");
                    continue;
                }
                nodes.insert(
                    key,
                    Node {
                        tree: fields[1].to_string(),
                        id: fields[2].to_string(),
                        feature: fields[3].to_string(),
                        threshold,
                        left,
                        right,
                        line,
                    },
                );
            }
            _ => push(&mut violations, 2, line, "E_MODEL_FIELDS"),
        }
    }

    if non_comment == 0 || !seen_header {
        push(&mut violations, 1, 1, "E_MODEL_HEADER");
    }
    if bias.is_none() {
        push(&mut violations, 2, 1, "E_MODEL_FIELDS");
    }

    for tree in trees.values() {
        if !nodes.contains_key(&(tree.id.clone(), tree.root.clone())) {
            push(&mut violations, 7, tree.line, "E_MODEL_REFERENCE");
        }
    }
    for node in nodes.values() {
        if !trees.contains_key(&node.tree) || !features.contains_key(&node.feature) {
            push(&mut violations, 7, node.line, "E_MODEL_REFERENCE");
            continue;
        }
        let feature = &features[&node.feature];
        if node.threshold < feature.min.saturating_sub(1) || node.threshold > feature.max {
            push(&mut violations, 6, node.line, "E_MODEL_RANGE");
        }
        for link in [&node.left, &node.right] {
            if let Child::Node(id) = link {
                if !nodes.contains_key(&(node.tree.clone(), id.clone())) {
                    push(&mut violations, 7, node.line, "E_MODEL_REFERENCE");
                }
            }
        }
    }

    // Topology and full-domain checks are completed by the command implementation.

    let mut product = 1u64;
    for feature in features.values() {
        product = product.saturating_mul((i64::from(feature.max) - i64::from(feature.min) + 1) as u64);
    }
    if features.len() > 8 || trees.len() > 12 || nodes.len() > 80 {
        push(&mut violations, 9, 1, "E_MODEL_LIMIT");
    }

    if let Some(winner) = violations.iter().min_by_key(|v| (v.priority, v.line)) {
        return Err(ContractError { token: winner.token, line: winner.line });
    }

    Ok(Model {
        bias: bias.unwrap().0,
        features,
        trees,
        nodes,
    })
}

pub fn canonical_model(model: &Model) -> String {
    let mut out = format!("BIAS|{}\n", model.bias);
    for feature in model.features.values() {
        out.push_str(&format!(
            "FEATURE|{}|{}|{}|{}\n",
            feature.id, feature.min, feature.max, feature.cost
        ));
    }
    for tree in model.trees.values() {
        out.push_str(&format!("TREE|{}|{}|{}\n", tree.id, tree.weight, tree.root));
    }
    for node in model.nodes.values() {
        out.push_str(&format!(
            "NODE|{}|{}|{}|{}|{}|{}\n",
            node.tree,
            node.id,
            node.feature,
            node.threshold,
            node.left.canonical(),
            node.right.canonical()
        ));
    }
    out
}

pub fn model_hash(model: &Model) -> String {
    hash_hex(canonical_model(model).as_bytes())
}
