//! Capability set carried by a compiled surface.

/// A set of capability names in sorted, de-duplicated form.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct CapabilitySet {
    names: Vec<String>,
}

impl CapabilitySet {
    pub fn from_flags(detached: bool, strict: bool) -> Self {
        let mut names = vec!["core".to_string()];
        if detached {
            names.push("detached".to_string());
        }
        if strict {
            names.push("strict".to_string());
        }
        names.sort();
        names.dedup();
        CapabilitySet { names }
    }

    pub fn names(&self) -> &[String] {
        &self.names
    }

    pub fn contains(&self, name: &str) -> bool {
        self.names.iter().any(|n| n == name)
    }
}
