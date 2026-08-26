//! Parse the interface description language into a canonical ABI descriptor.

mod parse;

pub use parse::parse_idl;

use docmodel::Value;

#[derive(Clone, Debug, Default, PartialEq)]
pub struct Descriptor {
    pub operations: Vec<Operation>,
    pub capabilities: Vec<String>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Operation {
    pub name: String,
    pub requires: String,
}

impl Descriptor {
    /// Canonical JSON of the descriptor: operations and capabilities sorted,
    /// compact separators, no host-specific data.
    pub fn canonical_json(&self) -> String {
        let mut ops = self.operations.clone();
        ops.sort_by(|a, b| a.name.cmp(&b.name));
        let op_values: Vec<Value> = ops
            .into_iter()
            .map(|op| {
                Value::Obj(vec![
                    ("name".to_string(), Value::Str(op.name)),
                    ("requires".to_string(), Value::Str(op.requires)),
                ])
            })
            .collect();

        let mut caps = self.capabilities.clone();
        caps.sort();
        caps.dedup();
        let cap_values: Vec<Value> = caps.into_iter().map(Value::Str).collect();

        let root = Value::Obj(vec![
            ("capabilities".to_string(), Value::Arr(cap_values)),
            ("operations".to_string(), Value::Arr(op_values)),
            ("schema".to_string(), Value::Int(1)),
        ]);
        docmodel::dump_compact(&root)
    }

    /// SHA-256 of the canonical descriptor bytes.
    pub fn fingerprint(&self) -> String {
        docmodel::sha256_hex(self.canonical_json().as_bytes())
    }
}
