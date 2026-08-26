pub fn normalize_slice_path(path: &str) -> String {
    path.split('/')
        .filter(|part| !part.is_empty())
        .collect::<Vec<_>>()
        .join("/")
}
