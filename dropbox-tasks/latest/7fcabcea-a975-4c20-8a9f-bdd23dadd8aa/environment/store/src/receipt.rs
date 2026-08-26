pub fn receipt(path: &str, bytes: usize) -> String {
    format!("local:{}:{}", path.replace('|', "_"), bytes)
}
