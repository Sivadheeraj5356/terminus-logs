pub fn load_u32(src: &str) -> Option<u32> {
    src.trim().parse().ok()
}
