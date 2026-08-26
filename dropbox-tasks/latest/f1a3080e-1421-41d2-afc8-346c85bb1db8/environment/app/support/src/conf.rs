//! Minimal reader for the release profile file. Supports the subset used by the
//! profile: `key = "string"`, `key = <integer>`, and `key = ["a", "b"]`.

use std::collections::BTreeMap;

#[derive(Debug, Default)]
pub struct Profile {
    strings: BTreeMap<String, String>,
    ints: BTreeMap<String, i64>,
    lists: BTreeMap<String, Vec<String>>,
}

impl Profile {
    pub fn parse(text: &str) -> Profile {
        let mut profile = Profile::default();
        for raw in text.lines() {
            let line = raw.trim();
            if line.is_empty() || line.starts_with('#') {
                continue;
            }
            let Some((key, value)) = line.split_once('=') else {
                continue;
            };
            let key = key.trim().to_string();
            let value = value.trim();
            if value.starts_with('[') && value.ends_with(']') {
                let inner = &value[1..value.len() - 1];
                let items: Vec<String> = inner
                    .split(',')
                    .map(|item| item.trim().trim_matches('"').to_string())
                    .filter(|item| !item.is_empty())
                    .collect();
                profile.lists.insert(key, items);
            } else if value.starts_with('"') && value.ends_with('"') && value.len() >= 2 {
                profile
                    .strings
                    .insert(key, value[1..value.len() - 1].to_string());
            } else if let Ok(n) = value.parse::<i64>() {
                profile.ints.insert(key, n);
            } else {
                profile.strings.insert(key, value.to_string());
            }
        }
        profile
    }

    pub fn string(&self, key: &str) -> Option<&str> {
        self.strings.get(key).map(|s| s.as_str())
    }
    pub fn int(&self, key: &str) -> Option<i64> {
        self.ints.get(key).copied()
    }
    pub fn list(&self, key: &str) -> Vec<String> {
        self.lists.get(key).cloned().unwrap_or_default()
    }
}
