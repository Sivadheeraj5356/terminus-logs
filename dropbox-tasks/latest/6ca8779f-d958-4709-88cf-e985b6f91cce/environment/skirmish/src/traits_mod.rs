pub fn has_trait(traits: &[String], name: &str) -> bool {
    traits.iter().any(|t| t == name)
}
