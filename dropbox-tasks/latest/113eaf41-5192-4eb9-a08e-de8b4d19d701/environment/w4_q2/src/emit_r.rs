pub fn emit_r(arm: &str, band: &str, seq: u32, epoch: u32, replay_hex: &str) -> String {
    format!(
        "GRTIROW|{}|{}|seq={}|epoch={}|replay={}",
        arm, band, seq, epoch, replay_hex
    )
}

pub fn fork_scope_tag(arm: &str, scope: u8) -> String {
    format!("FORK{}:{}", arm, scope)
}
