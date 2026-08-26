use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RuleFile {
    pub groups: Vec<RuleGroup>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RuleGroup {
    pub name: String,
    #[serde(default)]
    pub interval: Option<String>,
    pub rules: Vec<Rule>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum Rule {
    #[serde(rename = "recording")]
    Recording {
        record: String,
        expr: String,
        #[serde(default)]
        labels: Option<HashMap<String, String>>,
    },
    #[serde(rename = "alert")]
    Alert {
        alert: String,
        expr: String,
        #[serde(default)]
        for_duration: Option<String>,
        #[serde(default)]
        labels: Option<HashMap<String, String>>,
        #[serde(default)]
        annotations: Option<HashMap<String, String>>,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    pub strict_mode: bool,
    pub max_for_duration_seconds: u64,
    pub allow_digit_starting_names: bool,
    pub validate_templates: bool,
    pub label_regex_pattern: String,
    pub offset_bracket_required: bool,
    pub max_alert_duration_seconds: u64,
}

impl Default for Config {
    fn default() -> Self {
        Config {
            strict_mode: false,
            max_for_duration_seconds: 86400,
            allow_digit_starting_names: false,
            validate_templates: true,
            label_regex_pattern: String::from(r"^[a-zA-Z_][a-zA-Z0-9_]*=.+$"),
            offset_bracket_required: false,
            max_alert_duration_seconds: 86400,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Report {
    pub total_rule_groups: usize,
    pub total_rules: usize,
    pub valid_rules: usize,
    pub invalid_rules: usize,
    pub groups: Vec<GroupReport>,
    pub errors: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GroupReport {
    pub name: String,
    pub total_rules: usize,
    pub valid_rules: usize,
    pub invalid_rules: usize,
    pub errors: Vec<String>,
}
