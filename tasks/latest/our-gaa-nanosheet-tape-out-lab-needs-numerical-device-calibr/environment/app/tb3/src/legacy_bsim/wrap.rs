/// Optional BSIM-CMG style parameter inspection helpers used by lab notebooks.
pub fn inspect_drive_current(vth0: f64, u0: f64, vgs: f64, vds: f64) -> f64 {
    let vgt = (vgs - vth0).max(0.0);
    u0 * vgt * vds
}

pub fn inspect_param_lines(params: &[(&str, f64)]) -> Vec<String> {
    params
        .iter()
        .map(|(name, value)| format!("PREVIEW {}={}", name, value))
        .collect()
}
