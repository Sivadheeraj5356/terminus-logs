/// Telemetry band bucket labels; not witness replay gate.
pub fn fn_r5_stub(rc_band: u32) -> &'static str {
    match rc_band {
        0 => "bucket-zero",
        1..=300 => "bucket-low",
        301..=600 => "bucket-mid",
        _ => "bucket-high",
    }
}
