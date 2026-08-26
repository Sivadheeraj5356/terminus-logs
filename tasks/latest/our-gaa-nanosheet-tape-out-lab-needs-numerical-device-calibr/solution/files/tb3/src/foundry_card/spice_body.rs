use std::collections::BTreeMap;

use crate::{format_py_sci, FittedParams, CalibrationTapeout, PARAM_NAMES, SCHEMA_SPICE};

pub struct SpiceCard {
    pub header: String,
    pub body: String,
}

pub fn write_spice(
    path: &std::path::Path,
    tapeout: &CalibrationTapeout,
    fitted: &[FittedParams],
) -> Result<(), String> {
    let card = render_spice(tapeout, fitted);
    std::fs::write(path, card.body.clone() + "\n").map_err(|e| e.to_string())
}

pub fn render_spice(tapeout: &CalibrationTapeout, fitted: &[FittedParams]) -> SpiceCard {
    let mut lines = vec![
        format!("* schema {}", SCHEMA_SPICE),
        format!("* reference_temp_c {:.1}", tapeout.reference_temp_c),
        "* gaa compact model card".to_string(),
    ];
    for group in fitted {
        lines.push(format!("* split_group {}", group.split_group));
        for name in PARAM_NAMES {
            let value = group.values.get(name).copied().unwrap_or(0.0);
            let rendered = if name == "cgso" || name == "subth_weight" {
                format_py_sci(value)
            } else {
                // Match Python 3 `{value:.6f}` fixed-point formatting from spice-card.md.
                format!("{:.6}", value)
            };
            lines.push(format!(".param {}_{}={}", group.split_group, name, rendered));
        }
    }
    SpiceCard {
        header: SCHEMA_SPICE.to_string(),
        body: lines.join("\n"),
    }
}

pub fn param_lookup(fitted: &[FittedParams], split_group: &str) -> BTreeMap<String, f64> {
    fitted
        .iter()
        .find(|g| g.split_group == split_group)
        .map(|g| g.values.clone())
        .unwrap_or_default()
}

