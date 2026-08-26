/// Pick the holder (and its source file) when two merged slots combine.
pub fn choose_holder(
    left_holder: &str,
    left_file: &str,
    right_holder: &str,
    right_file: &str,
) -> (String, String) {
    if right_holder > left_holder {
        (right_holder.to_string(), right_file.to_string())
    } else {
        (left_holder.to_string(), left_file.to_string())
    }
}
