use blk_a::quick_a::quick_a;

pub fn flag_x(preview: &[u8]) -> String {
    let n = quick_a(preview);
    if n > 0 {
        "CHUNK_BAND=GREEN".to_string()
    } else {
        "CHUNK_BAND=RED".to_string()
    }
}
