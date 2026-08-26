use manifest::Entry;

pub const KNOWN_UNITS: &[&str] = &[
    "encoder.block0.q",
    "encoder.block0.v",
    "decoder.block0.o",
];

pub fn display_rows(xs: &[Entry]) -> Vec<String> {
    xs.iter()
        .enumerate()
        .map(|(i, x)| format!("{:03}:{}", i + 1, x.label.trim()))
        .collect()
}

pub fn known_unit(name: &str) -> bool {
    KNOWN_UNITS.iter().any(|u| *u == name)
}
