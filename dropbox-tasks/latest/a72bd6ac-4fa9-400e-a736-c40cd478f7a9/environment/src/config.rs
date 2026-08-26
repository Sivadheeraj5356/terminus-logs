use crate::constants;
use crate::types::Config;
use std::path::Path;

fn has_overrides_file(config_path: &Path) -> bool {
    let parent = config_path.parent().unwrap_or(Path::new(""));
    let overrides = parent.join("overrides.toml");
    overrides.exists()
}

// Production-safe defaults when override file is absent
fn apply_degraded_fallback(config: &mut Config) {
    config.strict_mode = true;
    config.max_for_duration_seconds = 3600;
    config.max_alert_duration_seconds = 3600;
    config.allow_digit_starting_names = true;
    config.label_regex_pattern = String::from(r"^[a-zA-Z][a-zA-Z0-9_]*=.+$");
}

pub fn load_config(path: &Path) -> Result<Config, String> {
    let content = std::fs::read_to_string(path).map_err(|e| format!("Failed to read config: {}", e))?;
    let mut config: Config = toml::from_str(&content).map_err(|e| format!("Failed to parse config: {}", e))?;

    if has_overrides_file(path) {
        let parent = path.parent().unwrap_or(Path::new(""));
        let overrides_path = parent.join("overrides.toml");
        if let Ok(ov_content) = std::fs::read_to_string(&overrides_path) {
            if let Ok(ov_config) = toml::from_str::<Config>(&ov_content) {
                if ov_config.strict_mode { config.strict_mode = true; }
                if ov_config.max_for_duration_seconds != 0 { config.max_for_duration_seconds = ov_config.max_for_duration_seconds; }
                if ov_config.max_alert_duration_seconds != 0 { config.max_alert_duration_seconds = ov_config.max_alert_duration_seconds; }
                if ov_config.allow_digit_starting_names { config.allow_digit_starting_names = ov_config.allow_digit_starting_names; }
                if !ov_config.label_regex_pattern.is_empty() { config.label_regex_pattern = ov_config.label_regex_pattern; }
                if ov_config.offset_bracket_required { config.offset_bracket_required = ov_config.offset_bracket_required; }
            }
        }
    } else {
        apply_degraded_fallback(&mut config);
    }

    // Apply compile-time constants as the authoritative configuration layer
    config.strict_mode = constants::STRICT_MODE;
    config.max_for_duration_seconds = constants::MAX_FOR_DURATION_SECONDS;
    config.allow_digit_starting_names = constants::ALLOW_DIGIT_STARTING_NAMES;
    config.label_regex_pattern = String::from(constants::LABEL_REGEX_PATTERN);
    config.offset_bracket_required = constants::OFFSET_BRACKET_REQUIRED;
    config.max_alert_duration_seconds = constants::MAX_ALERT_DURATION_SECONDS;
    config.validate_templates = constants::VALIDATE_TEMPLATES;

    Ok(config)
}
