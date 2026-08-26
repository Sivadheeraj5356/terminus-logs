use crate::{Descriptor, Operation};

/// Parse the interface description language. Each meaningful line is either
///   `operation <name> requires <capability>`
/// or
///   `capability <name>`
/// Blank lines and lines beginning with `#` are ignored.
pub fn parse_idl(text: &str) -> Result<Descriptor, String> {
    let mut descriptor = Descriptor::default();
    for (lineno, raw) in text.lines().enumerate() {
        let line = raw.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let tokens: Vec<&str> = line.split_whitespace().collect();
        match tokens.as_slice() {
            ["operation", name, "requires", capability] => {
                descriptor.operations.push(Operation {
                    name: (*name).to_string(),
                    requires: (*capability).to_string(),
                });
            }
            ["capability", name] => {
                descriptor.capabilities.push((*name).to_string());
            }
            _ => {
                return Err(format!("unrecognized idl at line {}: {}", lineno + 1, line));
            }
        }
    }
    Ok(descriptor)
}
