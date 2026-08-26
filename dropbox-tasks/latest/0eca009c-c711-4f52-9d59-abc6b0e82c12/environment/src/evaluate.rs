use crate::types::{Child, Evaluation, Model, Vote};
use std::collections::BTreeMap;

pub fn evaluate(model: &Model, values: &BTreeMap<String, i32>) -> Evaluation {
    let mut score = model.bias;
    let mut votes = Vec::with_capacity(model.trees.len());
    for tree in model.trees.values() {
        let mut current = tree.root.as_str();
        let leaf = loop {
            let node = &model.nodes[&(tree.id.clone(), current.to_string())];
            let value = values[&node.feature];
            let branch = if value <= node.threshold { &node.left } else { &node.right };
            match branch {
                Child::Leaf(value) => break *value,
                Child::Node(next) => current = next,
            }
        };
        let vote = tree.weight * leaf;
        score += vote;
        votes.push(Vote { tree: tree.id.clone(), leaf, vote });
    }
    Evaluation { score, prediction: if score > 0 { "POS" } else { "NEG" }, votes }
}
